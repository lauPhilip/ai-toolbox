import streamlit as st
import weaviate.classes.config as wvc
from weaviate.classes.query import Filter
from pypdf import PdfReader
import time

# --- 1. CONNECTION & SESSION STATE ---
from app import client # Centralized Weaviate client

# Security: Ensure only staff can access the Architect
if st.session_state.get("role") != "teacher":
    st.error("Access Denied: Internal Staff Credentials Required.")
    st.stop()

# Initialize dynamic keys for form resetting
if "assign_reset_key" not in st.session_state:
    st.session_state.assign_reset_key = 0
if "edit_assign_data" not in st.session_state:
    st.session_state.edit_assign_data = None

user_email = st.session_state.get("email")

# --- 2. UTILITY: RUBRIC EXTRACTION ---
def extract_rubric(file):
    try:
        reader = PdfReader(file)
        return " ".join([page.extract_text() for page in reader.pages])
    except Exception as e:
        st.error(f"Rubric Extraction Error: {e}")
        return ""

# --- 3. THE ARCHITECT INTERFACE ---
st.title("📝 Assignment Architect")
st.markdown("##### Design assignment parameters, learning outcomes, and internal grading rubrics.")

# Fetch official courses linked to this teacher
registry = client.collections.get("CourseRegistry")
reg_resp = registry.query.fetch_objects(
    filters=Filter.by_property("responsible_email").equal(user_email) | 
            Filter.by_property("teacher_emails").contains_any([user_email]),
    return_properties=["course_name", "course_id"],
    limit=100
)

course_map = {f"{o.properties['course_name']} ({o.properties['course_id']})": 
              {"name": o.properties['course_name'], "id": o.properties['course_id']} 
              for o in reg_resp.objects}

tab_create, tab_active = st.tabs(["🆕 Build/Edit Assignment", "📋 Active Assignments"])

# --- TAB: CREATE OR EDIT ---
with tab_create:
    is_editing = st.session_state.edit_assign_data is not None
    edit_data = st.session_state.edit_assign_data or {}
    
    st.subheader("🛠️ Edit Assignment" if is_editing else "🚀 Deploy New Assignment")
    
    if not course_map:
        st.warning("⚠️ No courses found. Please register a course in the Registry first.")
    else:
        # Form-style container using dynamic keys for instant clearing
        with st.container(border=True):
            f_title = st.text_input("Assignment Title", value=edit_data.get('title', ""), 
                                   key=f"title_{st.session_state.assign_reset_key}")
            
            # Find index for course selection during edit
            c_list = list(course_map.keys())
            c_idx = 0
            if is_editing:
                for i, label in enumerate(c_list):
                    if course_map[label]["id"] == edit_data.get("course_id"):
                        c_idx = i
                        break
            
            f_course_label = st.selectbox("Assign to Registered Course", options=c_list, index=c_idx, 
                                         key=f"course_{st.session_state.assign_reset_key}")
            
            col1, col2 = st.columns(2)
            with col1:
                f_desc = st.text_area("Mission Objective (Visible to Students)", 
                                     value=edit_data.get('desc', ""), height=250, 
                                     key=f"desc_{st.session_state.assign_reset_key}")
            with col2:
                f_outcomes = st.text_area("Learning Outcomes", 
                                         value=edit_data.get('outcomes', ""), height=250, 
                                         key=f"out_{st.session_state.assign_reset_key}")

            st.write("---")
            st.markdown("### 🔑 The Master Answer Scheme")
            st.caption("This PDF is analyzed by course-bot for internal grading and remains hidden from students.")
            
            if is_editing:
                st.info("Current Rubric is locked in the vault. Uploading a new PDF will overwrite it.")

            f_rubric_file = st.file_uploader("Upload Rubric / Answer Key (PDF)", type=['pdf'], 
                                           key=f"file_{st.session_state.assign_reset_key}")
            
            c_save, c_cancel = st.columns(2)
            
            submit_btn = c_save.button("💾 Update Assignment" if is_editing else "🚀 Deploy Assignment", 
                                       type="primary", use_container_width=True)
            
            if submit_btn:
                if f_title and f_desc:
                    with st.spinner("oploading assignment..."):
                        # Auto-Provisioning Collection
                        if not client.collections.exists("AssignmentRegistry"):
                            client.collections.create(
                                name="AssignmentRegistry",
                                properties=[
                                    wvc.Property(name="title", data_type=wvc.DataType.TEXT),
                                    wvc.Property(name="description", data_type=wvc.DataType.TEXT),
                                    wvc.Property(name="learning_outcomes", data_type=wvc.DataType.TEXT),
                                    wvc.Property(name="course_id", data_type=wvc.DataType.TEXT),
                                    wvc.Property(name="course_name", data_type=wvc.DataType.TEXT),
                                    wvc.Property(name="creator_email", data_type=wvc.DataType.TEXT),
                                    wvc.Property(name="rubric_text", data_type=wvc.DataType.TEXT),
                                    wvc.Property(name="status", data_type=wvc.DataType.TEXT),
                                ]
                            )
                        
                        assign_col = client.collections.get("AssignmentRegistry")
                        
                        # Handle Rubric data
                        final_rubric = edit_data.get("rubric_text", "")
                        if f_rubric_file:
                            final_rubric = extract_rubric(f_rubric_file)

                        props = {
                            "title": f_title,
                            "description": f_desc,
                            "learning_outcomes": f_outcomes,
                            "course_id": course_map[f_course_label]["id"],
                            "course_name": course_map[f_course_label]["name"],
                            "creator_email": user_email,
                            "rubric_text": final_rubric,
                            "status": "Live"
                        }

                        if is_editing:
                            assign_col.data.update(uuid=edit_data['uuid'], properties=props)
                            st.success("Assignment updated.")
                        else:
                            assign_col.data.insert(properties=props)
                            st.success("New assignment deployed.")
                        
                        st.session_state.edit_assign_data = None
                        st.session_state.assign_reset_key += 1
                        time.sleep(1)
                        st.rerun()

            if c_cancel.button("❌ Clear / Cancel", use_container_width=True):
                st.session_state.edit_assign_data = None
                st.session_state.assign_reset_key += 1
                st.rerun()

# --- TAB: MISSION CONTROL ---
with tab_active:
    st.subheader("Your Deployed Assignments")
    if client.collections.exists("AssignmentRegistry"):
        assign_col = client.collections.get("AssignmentRegistry")
        my_assigns = assign_col.query.fetch_objects(
            filters=Filter.by_property("creator_email").equal(user_email),
            limit=50
        )
        
        if not my_assigns.objects:
            st.info("No active assignments.")
        else:
            for a in my_assigns.objects:
                with st.container(border=True):
                    col_info, col_actions = st.columns([0.7, 0.3])
                    with col_info:
                        st.write(f"**{a.properties['title']}**")
                        st.caption(f"Course: {a.properties['course_name']} | ID: {a.properties['course_id']}")
                    
                    with col_actions:
                        a_c1, a_c2 = st.columns(2)
                        if a_c1.button("📝", key=f"edit_ctrl_{a.uuid}", help="Edit Mission"):
                            st.session_state.edit_assign_data = {
                                "uuid": a.uuid, "title": a.properties['title'],
                                "desc": a.properties['description'], "outcomes": a.properties['learning_outcomes'],
                                "course_id": a.properties['course_id'], "rubric_text": a.properties['rubric_text']
                            }
                            st.rerun()
                        
                        if a_c2.button("🗑️", key=f"del_ctrl_{a.uuid}", help="Recall Mission"):
                            assign_col.data.delete_by_id(a.uuid)
                            st.toast(f"Mission '{a.properties['title']}' recalled.")
                            time.sleep(0.5)
                            st.rerun()
    else:
        st.info("The Assignment Registry hasn't been initialized yet.")