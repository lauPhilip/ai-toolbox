import streamlit as st
import weaviate
import weaviate.classes as wvc
from weaviate.classes.init import Auth
from weaviate.classes.query import Filter, Sort
from st_copy import copy_button

# --- 1. CONNECTION ---
@st.cache_resource
def get_weaviate_client():
    return weaviate.connect_to_weaviate_cloud(
        cluster_url=st.secrets["WEAVIATE_URL"],
        auth_credentials=Auth.api_key(st.secrets["WEAVIATE_API_KEY"]),
    )

client = get_weaviate_client()
prompt_col = client.collections.get("StudentPromptLibrary")

# Initialize edit state
if "edit_student_data" not in st.session_state:
    st.session_state.edit_student_data = None

st.title("📋 Student Prompt Library")
role = st.session_state.get("role", "student").lower()
current_user = st.session_state.get('name', 'Staff')

# --- 2. TEACHER: CREATE / EDIT TAB ---
if role == "teacher":
    mode = "Edit Template" if st.session_state.edit_student_data else "Create New Student Template"
    
    with st.expander(f"➕ {mode}", expanded=bool(st.session_state.edit_student_data)):
        edit_data = st.session_state.edit_student_data or {}
        
        prog_options = ["Bachelor", "Master", "Both"]
        saved_prog = edit_data.get('prog')
        
        try:
            default_index = prog_options.index(saved_prog) if saved_prog in prog_options else 0
        except ValueError:
            default_index = 0

        with st.form("student_prompt_form", clear_on_submit=True):
            f_title = st.text_input("Prompt Title", value=edit_data.get('title', ""))
            f_desc = st.text_input("Description", value=edit_data.get('desc', ""))
            f_course = st.text_input("Course Name", value=edit_data.get('course', ""))
            f_prog = st.selectbox("Program Level", prog_options, index=default_index)
            f_text = st.text_area("The Actual Prompt", value=edit_data.get('text', ""), height=150)
            
            c1, c2 = st.columns(2)
            save_clicked = c1.form_submit_button("💾 Save to Library")
            cancel_clicked = c2.form_submit_button("❌ Cancel / Clear")
            
            if save_clicked:
                if f_title and f_text:
                    props = {
                        "title": f_title, 
                        "prompt_text": f_text, 
                        "description": f_desc,
                        "course_name": f_course, 
                        "program": f_prog, 
                        "creator": current_user
                    }
                    if st.session_state.edit_student_data:
                        prompt_col.data.update(uuid=edit_data['uuid'], properties=props)
                        st.session_state.edit_student_data = None
                        st.success("Template updated!")
                    else:
                        props["usage_count"] = 0
                        prompt_col.data.insert(props)
                        st.success("New template published!")
                    
                    st.rerun()
                else:
                    st.warning("Please provide a Title and Prompt text.")

            if cancel_clicked:
                st.session_state.edit_student_data = None
                st.rerun()

# --- 3. SEARCH & FILTER ---
st.write("### 🔍 Search & Filter")
col_search, col_prog, col_course = st.columns([2, 1, 1])
with col_search:
    search_query = st.text_input("Search prompts...", placeholder="Keywords...")
with col_prog:
    prog_filter = st.selectbox("Level", ["All", "Bachelor", "Master"])
with col_course:
    all_objs = prompt_col.query.fetch_objects(return_properties=["course_name"])
    unique_courses = sorted(list(set([o.properties.get('course_name') for o in all_objs.objects if o.properties.get('course_name')])))
    course_filter = st.selectbox("Course", ["All"] + unique_courses)

# --- 4. DATA RETRIEVAL ---
filters = None
if prog_filter != "All":
    filters = Filter.by_property("program").equal(prog_filter)
if course_filter != "All":
    f = Filter.by_property("course_name").equal(course_filter)
    filters = (filters & f) if filters else f

results = prompt_col.query.bm25(query=search_query, filters=filters, limit=20) if search_query else \
          prompt_col.query.fetch_objects(filters=filters, limit=20)

# --- 5. DISPLAY RESULTS ---
st.divider()
if results.objects:
    for obj in results.objects:
        p = obj.properties
        is_owner = (p.get('creator') == current_user)
        
        with st.container(border=True):
            st.write(f"### {p.get('title')}")
            st.caption(f"🎓 {p.get('program')} | 📚 {p.get('course_name')} | 👤 {p.get('creator')}")
            st.write(p.get('description'))
            
            # Text is visible but also copyable via the button below
            st.code(p.get('prompt_text'), language="text")
            
            # Action Row
            btn_cols = st.columns([0.3, 0.15, 0.15, 0.4])
            
            with btn_cols[0]:
                # Updated Copy Button implementation
                copy_button(
                    p.get('prompt_text'),
                    icon="st",
                    tooltip="Copy this prompt to clipboard",
                    copied_label="✅ Copied!",
                    key=f"copy_{obj.uuid}"
                )
            
            if role == "teacher" and is_owner:
                with btn_cols[1]:
                    if st.button("📝 Edit", key=f"ed_{obj.uuid}"):
                        st.session_state.edit_student_data = {
                            "uuid": obj.uuid, "title": p['title'], "desc": p['description'],
                            "course": p['course_name'], "prog": p['program'], "text": p['prompt_text']
                        }
                        st.rerun()
                with btn_cols[2]:
                    if st.button("🗑️ Delete", key=f"del_{obj.uuid}"):
                        prompt_col.data.delete_by_id(obj.uuid)
                        st.rerun()
else:
    st.info("No prompts found matching your criteria.")