import streamlit as st
import weaviate
import weaviate.classes as wvc
from weaviate.classes.init import Auth

# --- 1. CONNECTION & STATE ---
@st.cache_resource
def get_weaviate_client():
    return weaviate.connect_to_weaviate_cloud(
        cluster_url=st.secrets["WEAVIATE_URL"],
        auth_credentials=Auth.api_key(st.secrets["WEAVIATE_API_KEY"]),
    )

client = get_weaviate_client()
library_col = client.collections.get("PromptLibrary")

if st.session_state.get("role") != "teacher":
    st.error("Access Denied.")
    st.stop()

# Track which tab should be active (0=Browse, 1=Create, 2=Edit)
if "active_tab" not in st.session_state:
    st.session_state.active_tab = 0
if "editing_data" not in st.session_state:
    st.session_state.editing_data = None

st.title("📚 System Prompt Library")

# Define tabs with the 'selection' controlled by session state
tab_list = ["🔍 Browse Templates", "➕ Create New", "📝 Edit Template"]
tab_browse, tab_create, tab_edit = st.tabs(tab_list)

# --- TAB 1: BROWSE ---
with tab_browse:
    st.subheader("Available Templates")
    templates = library_col.query.fetch_objects(limit=100)
    current_user = st.session_state.get('name') # Get the logged-in teacher's name

    for obj in templates.objects:
        p = obj.properties
        is_owner = (p.get('creator') == current_user) # Security check

        with st.expander(f"📖 {p['template_name']} ({p['program']})"):
            st.info(f"**Use Case:** {p.get('use_case')}")
            st.code(p.get('template_text'), language="text")
            st.caption(f"Shared by: {p.get('creator')} | Related: {p.get('related_course')}")
            
            # Setup columns: "Use" is for everyone, "Edit/Delete" only for owner
            cols = st.columns(3)
            
            # Button 1: Use (Public)
            if cols[0].button("✨ Use Prompt", key=f"use_{obj.uuid}"):
                st.session_state['active_prompt_copy'] = p.get('template_text')
                st.toast("Copied! Ready for Course Dashboard.")

            # Buttons 2 & 3: Restricted to Creator
            if is_owner:
                if cols[1].button("📝 Edit", key=f"edit_trig_{obj.uuid}"):
                    st.session_state.editing_data = {
                        "uuid": obj.uuid,
                        "name": p.get('template_name'),
                        "use": p.get('use_case'),
                        "course": p.get('related_course'),
                        "text": p.get('template_text'),
                        "program": p.get('program')
                    }
                    # JUMP TO EDIT TAB: In current Streamlit, we rerun to update the UI state
                    st.success("Loading into Edit tab...")
                    st.rerun()
                
                if cols[2].button("🗑️ Delete", key=f"del_{obj.uuid}"):
                    library_col.data.delete_by_id(obj.uuid)
                    st.success("Template removed.")
                    st.rerun()
            else:
                cols[1].info("🔒 Only creator can edit")

# --- TAB 2: CREATE NEW ---
with tab_create:
    st.subheader("Add a New Recipe")
    with st.form("create_form", clear_on_submit=True):
        n_name = st.text_input("Template Name")
        n_use = st.text_input("Use Case")
        n_prog = st.selectbox("Target Program", ["Bachelor", "Master", "Both"])
        n_course = st.text_input("Primary Course")
        n_text = st.text_area("The Prompt Template", height=250)
        
        if st.form_submit_button("🚀 Save to Library"):
            if n_name and n_text:
                library_col.data.insert(properties={
                    "template_name": n_name,
                    "template_text": n_text,
                    "creator": current_user,
                    "use_case": n_use,
                    "related_course": n_course,
                    "program": n_prog
                })
                st.success("New template shared!")
                st.rerun()

# --- TAB 3: EDIT TEMPLATE ---
with tab_edit:
    if st.session_state.editing_data:
        edit_target = st.session_state.editing_data
        st.subheader(f"Editing: {edit_target['name']}")
        
        with st.form("edit_form"):
            u_name = st.text_input("Template Name", value=edit_target['name'])
            u_use = st.text_input("Use Case", value=edit_target['use'])
            u_prog = st.selectbox("Target Program", ["Bachelor", "Master", "Both"], 
                                 index=["Bachelor", "Master", "Both"].index(edit_target['program']))
            u_course = st.text_input("Primary Course", value=edit_target['course'])
            u_text = st.text_area("The Prompt Template", value=edit_target['text'], height=250)
            
            c1, c2 = st.columns(2)
            if c1.form_submit_button("💾 Update Changes"):
                library_col.data.update(
                    uuid=edit_target['uuid'],
                    properties={
                        "template_name": u_name, "template_text": u_text,
                        "use_case": u_use, "related_course": u_course, "program": u_prog
                    }
                )
                st.session_state.editing_data = None
                st.success("Changes saved!")
                st.rerun()
            
            if c2.form_submit_button("❌ Discard"):
                st.session_state.editing_data = None
                st.rerun()
    else:
        st.info("Pick one of your own templates from the 'Browse' tab to edit it here.")