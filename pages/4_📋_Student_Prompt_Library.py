import streamlit as st
import weaviate
import weaviate.classes as wvc
from weaviate.classes.init import Auth
from weaviate.classes.query import Filter
from st_copy import copy_button
import time

# --- 1. CONNECTION ---
@st.cache_resource
def get_weaviate_client():
    return weaviate.connect_to_weaviate_cloud(
        cluster_url=st.secrets["WEAVIATE_URL"],
        auth_credentials=Auth.api_key(st.secrets["WEAVIATE_API_KEY"]),
    )

client = get_weaviate_client()
prompt_col = client.collections.get("StudentPromptLibrary")
course_registry = client.collections.get("CourseRegistry")
bot_memory = client.collections.get("CourseBotMemory")

# Initialize edit state
if "edit_student_data" not in st.session_state:
    st.session_state.edit_student_data = None

st.title("📋 Student Prompt Library")
role = st.session_state.get("role", "student").lower()
user_email = st.session_state.get("email") # Anchored in auth.py
current_user_name = st.session_state.get('name', 'Staff')

# --- 2. TEACHER: CREATE / EDIT HUB ---
if role == "teacher":
    mode = "Edit Template" if st.session_state.edit_student_data else "Create New Student Template"
    
    with st.expander(f"➕ {mode}", expanded=bool(st.session_state.edit_student_data)):
        edit_data = st.session_state.edit_student_data or {}
        
        # Fetch official courses for selection
        registry_resp = course_registry.query.fetch_objects(
            filters=Filter.by_property("responsible_email").equal(user_email) | 
                    Filter.by_property("teacher_emails").contains_any([user_email]),
            return_properties=["course_name", "course_id"],
            limit=100
        )
        
        course_map = {f"{o.properties['course_name']} ({o.properties['course_id']})": 
                      {"name": o.properties['course_name'], "id": o.properties['course_id']} 
                      for o in registry_resp.objects}

        if not course_map:
            st.warning("⚠️ No courses found in your Registry. Please register a course first.")
        else:
            with st.form("student_prompt_form", clear_on_submit=True):
                f_title = st.text_input("Template Title", value=edit_data.get('title', ""))
                f_desc = st.text_input("Quick Description", value=edit_data.get('desc', ""))
                
                # Course Selection
                saved_id = edit_data.get('course_id')
                course_list = list(course_map.keys())
                c_idx = 0
                if saved_id:
                    for i, label in enumerate(course_list):
                        if course_map[label]["id"] == saved_id:
                            c_idx = i
                            break
                
                f_course_label = st.selectbox("Assign to Course", course_list, index=c_idx)
                selected_course_info = course_map[f_course_label]

                # Bot Verification (Internal check for the teacher)
                bot_check = bot_memory.query.fetch_objects(
                    filters=Filter.by_property("course_id").equal(selected_course_info["id"]),
                    return_properties=["bot_name"], limit=500
                )
                bots = sorted(list(set([b.properties.get('bot_name', 'Standard Bot') for b in bot_check.objects])))
                st.caption(f"🤖 Verified Bots for this course: {', '.join(bots) if bots else 'None yet.'}")
                
                col_a, col_b = st.columns(2)
                with col_a:
                    f_prog = st.selectbox("Program Level", ["Bachelor", "Master", "Both"], 
                                         index=["Bachelor", "Master", "Both"].index(edit_data.get('prog', 'Bachelor')))
                with col_b:
                    f_cat = st.selectbox("Category", ["Exam Prep", "Analysis", "Writing", "General"], 
                                        index=["Exam Prep", "Analysis", "Writing", "General"].index(edit_data.get('category', 'General')))
                
                f_text = st.text_area("The Actual Prompt", value=edit_data.get('text', ""), height=200)
                
                c1, c2 = st.columns(2)
                if c1.form_submit_button("💾 Save Template", type="primary", use_container_width=True):
                    if f_title and f_text:
                        props = {
                            "title": f_title, 
                            "prompt_text": f_text, 
                            "description": f_desc,
                            "course_name": selected_course_info["name"],
                            "course_id": selected_course_info["id"],
                            "program": f_prog, 
                            "creator": current_user_name,
                            "creator_email": user_email,
                            "category": f_cat
                        }
                        if st.session_state.edit_student_data:
                            prompt_col.data.update(uuid=edit_data['uuid'], properties=props)
                            st.session_state.edit_student_data = None
                            st.success("Template Updated.")
                        else:
                            prompt_col.data.insert(props)
                            st.success("Template Published.")
                        time.sleep(1)
                        st.rerun()

                if c2.form_submit_button("❌ Cancel", use_container_width=True):
                    st.session_state.edit_student_data = None
                    st.rerun()

# --- 3. SEARCH & FILTER ---
st.write("### 🔍 Search Library")
s1, s2, s3 = st.columns([2, 1, 1])
with s1:
    search_q = st.text_input("Keyword search...", key="search_lib")
with s2:
    p_filt = st.selectbox("Level", ["All", "Bachelor", "Master", "Both"])
with s3:
    lib_objs = prompt_col.query.fetch_objects(return_properties=["course_name"])
    lib_courses = sorted(list(set([o.properties.get('course_name') for o in lib_objs.objects if o.properties.get('course_name')])))
    c_filt = st.selectbox("Course", ["All"] + lib_courses)

# --- 4. DATA RETRIEVAL ---
filters = None
if p_filt != "All":
    filters = Filter.by_property("program").equal(p_filt)
if c_filt != "All":
    cf = Filter.by_property("course_name").equal(c_filt)
    filters = (filters & cf) if filters else cf

results = prompt_col.query.bm25(query=search_q, filters=filters, limit=20) if search_q else \
          prompt_col.query.fetch_objects(filters=filters, limit=20)

# --- 5. THE GALLERY ---
st.divider()
if results.objects:
    for obj in results.objects:
        p = obj.properties
        is_owner = (p.get('creator_email') == user_email)
        
        with st.container(border=True):
            st.write(f"### {p.get('title')}")
            st.caption(f"🎓 {p.get('program')} | 📚 {p.get('course_name')} | 👤 {p.get('creator')}")
            st.write(p.get('description'))
            
            st.code(p.get('prompt_text'), language="text")
            
            # Action Row
            btn_cols = st.columns([0.3, 0.15, 0.15, 0.4])
            
            with btn_cols[0]:
                # REINTEGRATED: The Copy Button
                copy_button(
                    p.get('prompt_text'),
                    icon="st",
                    tooltip="Copy this prompt to clipboard",
                    copied_label="✅ Copied!",
                    key=f"copy_{obj.uuid}"
                )
            
            if role == "teacher" and is_owner:
                with btn_cols[1]:
                    if st.button("📝 Edit", key=f"ed_{obj.uuid}", use_container_width=True):
                        st.session_state.edit_student_data = {
                            "uuid": obj.uuid, "title": p['title'], "desc": p['description'],
                            "course_id": p['course_id'], "prog": p['program'], "text": p['prompt_text'],
                            "category": p.get('category', 'General')
                        }
                        st.rerun()
                with btn_cols[2]:
                    if st.button("🗑️", key=f"del_{obj.uuid}", use_container_width=True):
                        prompt_col.data.delete_by_id(obj.uuid)
                        st.rerun()
else:
    st.info("No templates found matching your criteria.")