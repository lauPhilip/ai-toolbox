import streamlit as st
import weaviate
from weaviate.classes.init import Auth
import weaviate.classes as wvc
from weaviate.classes.query import Filter
from pypdf import PdfReader
from pptx import Presentation
import uuid

import streamlit as st

# Debugging: Uncomment the line below if you still get denied to see what the app "sees"
#st.write(f"Debug: Status={st.session_state.get('authentication_status')}, Role={st.session_state.get('role')}")

if st.session_state.get("authentication_status") is not True:
    st.switch_page("main.py")
    st.stop()

# Ensure the role check is exact
if str(st.session_state.get("role")).lower() != "teacher":
    st.error(f"Access Denied: Your role is '{st.session_state.get('role')}', but 'teacher' is required.")
    if st.button("Back to Student Portal"):
        st.switch_page("main.py")
    st.stop()
# --- WEAVIATE CORE ---
# Pulling credentials from .streamlit/secrets.toml
wcd_url = st.secrets["WEAVIATE_URL"]
wcd_api_key = st.secrets["WEAVIATE_API_KEY"]

client = weaviate.connect_to_weaviate_cloud(
    cluster_url=wcd_url,
    auth_credentials=Auth.api_key(wcd_api_key),
)

# Targeting the collection from your console screenshot
collection = client.collections.get("CourseBotMemory")

st.title(f"👨‍🏫 {st.session_state['name']}'s Course Dashboard")

# --- UTILITY: FILE EXTRACTION ---
def extract_text(file):
    if file.name.endswith(".pdf"):
        reader = PdfReader(file)
        return " ".join([page.extract_text() for page in reader.pages])
    elif file.name.endswith(".pptx"):
        prs = Presentation(file)
        return " ".join([shape.text for slide in prs.slides for shape in slide.shapes if hasattr(shape, "text")])
    return ""

# --- DASHBOARD TABS ---
tab_manage, tab_upload = st.tabs(["📚 My Course Bots", "➕ Create Course Bot"])

with tab_upload:
    st.subheader("Upload to Weaviate")
    course_name = st.text_input("Course Name (e.g., Advanced Web Development 48020PU018)")
    program_level = st.selectbox("Level", ["Bachelor", "Master"])

    st.write("---")
    st.markdown("### 🤖 Bot Configuration")
    system_prompt = st.text_area(
        "System Prompt", 
        value="You are a professional academic assistant. Use ONLY the provided context to answer.",
        help="This defines how the AI behaves and its limitations."
    )
    temperature = st.slider("Creativity (Temperature)", 0.0, 1.0, 0.2, 0.1)
    st.write("---")

    uploaded_files = st.file_uploader("Upload PDFs or PowerPoints", accept_multiple_files=True)
    
    if st.button("Vectorize & Save"):
        if course_name and uploaded_files:
            with st.spinner("course-bot is processing..."):
                for file in uploaded_files:
                    raw_text = extract_text(file)
                    # Simple chunking (1000 chars)
                    chunks = [raw_text[i:i+1000] for i in range(0, len(raw_text), 1000)]
                    
                    for i, chunk in enumerate(chunks):
                        collection.data.insert(
                            properties={
                                "doc_title": file.name,
                                "chunk_id": str(uuid.uuid4()),
                                "chunk": chunk,
                                "course_name": course_name,
                                "course_administrator": st.session_state['username'],
                                "program": program_level,
                                "system_prompt": system_prompt,
                                "temperature": float(temperature)
                            }
                        )
            st.success(f"Successfully added {len(uploaded_files)} files to {course_name}!")
        else:
            st.warning("Course Name and Files are required.")

with tab_manage:
    st.subheader("Your Active Courses")

    # 1. Fetch unique courses managed by this specific teacher
    results = collection.query.fetch_objects(
        filters=Filter.by_property("course_administrator").equal(st.session_state['username']),
        return_properties=["course_name"],
        limit=1000 
    )

    my_courses = sorted(list(set([obj.properties['course_name'] for obj in results.objects])))
    
    if my_courses:
        selected_course = st.selectbox("Select Course to Manage", my_courses)
        
        # --- EDIT BOT CONFIGURATION SECTION ---
        st.write("---")
        st.markdown(f"### ⚙️ Bot Configuration for: {selected_course}")
        
        # Fetch current config from one chunk of this course to pre-fill the fields
        config_sample = collection.query.fetch_objects(
            filters=Filter.by_property("course_name").equal(selected_course),
            return_properties=["system_prompt", "temperature"],
            limit=1
        )
        
        # Set defaults in case it's an older course with empty fields
        current_p = "You are a professional academic assistant. Use ONLY the provided context to answer."
        current_t = 0.2
        current_lvl = "Bachelor"
        
        if config_sample.objects:
            obj = config_sample.objects[0]
            # Use existing values if they aren't None
            current_p = obj.properties.get("system_prompt") or current_p
            current_lvl = obj.properties.get("program") or current_lvl
            current_t = obj.properties.get("temperature") if obj.properties.get("temperature") is not None else current_t

        # UI for editing
        edit_p = st.text_area("System Prompt", value=current_p, help="Instructions for how the AI should behave.")
        edit_t = st.slider("Temperature (Creativity)", 0.0, 1.0, float(current_t), 0.1)
        
        if st.button("💾 Save Bot Settings"):
            with st.spinner("Updating bot personality..."):
                # 1. Fetch all object IDs for this course
                targets = collection.query.fetch_objects(
                    filters=Filter.by_property("course_name").equal(selected_course),
                    return_properties=[], # We only need the UUIDs
                    limit=10000 
                )
                
                # 2. Update each object individually
                # (Weaviate v4 handles this very fast internally)
                for obj in targets.objects:
                    collection.data.update(
                        uuid=obj.uuid,
                        properties={
                            "system_prompt": edit_p,
                            "temperature": edit_t
                        }
                    )
            
            st.success(f"Bot personality updated for all {len(targets.objects)} chunks in {selected_course}!")
            st.rerun()
            
        st.write("---")
        st.markdown(f"### ➕ Add Content to {selected_course}")

        # 1. Use a dynamic key based on a counter to force a reset
        if "uploader_key" not in st.session_state:
            st.session_state.uploader_key = 0

        new_files = st.file_uploader(
            "Upload more PDFs or PowerPoints", 
            accept_multiple_files=True, 
            key=f"manage_upload_{st.session_state.uploader_key}"
        )

        if st.button("🚀 Upload & Process New Files"):
            if new_files:
                with st.spinner("L.U.M.A. is integrating new knowledge..."):
                    for file in new_files:
                        raw_text = extract_text(file)
                        chunks = [raw_text[i:i+1000] for i in range(0, len(raw_text), 1000)]
                        
                        for i, chunk in enumerate(chunks):
                            collection.data.insert(
                                properties={
                                    "doc_title": file.name,
                                    "chunk_id": str(uuid.uuid4()),
                                    "chunk": chunk,
                                    "course_name": selected_course,
                                    "course_administrator": st.session_state['username'],
                                    "program": current_lvl,
                                    "system_prompt": edit_p, 
                                    "temperature": edit_t
                                }
                            )
                
                # 2. Increment the key to force the uploader to clear
                st.session_state.uploader_key += 1
                st.success(f"Added {len(new_files)} files to {selected_course}!")
                
                # 3. Rerun now happens with a new widget key
                st.rerun() 
            else:
                st.warning("Please select files first.")

        # --- FILE LIST SECTION ---
        st.write("---")
        file_results = collection.query.fetch_objects(
            filters=Filter.by_property("course_name").equal(selected_course),
            return_properties=["doc_title"],
            limit=1000
        )
        unique_files = sorted(list(set([obj.properties['doc_title'] for obj in file_results.objects])))
        
        st.write(f"Existing Files in **{selected_course}**:")
        for f in unique_files:
            col1, col2 = st.columns([0.8, 0.2])
            col1.text(f"📄 {f}")
            if col2.button("🗑️", key=f"del_{f}"):
                collection.data.delete_many(
                    where=wvc.query.Filter.by_property("doc_title").equal(f) &
                          wvc.query.Filter.by_property("course_name").equal(selected_course)
                )
                st.rerun()
    else:
        st.info("You haven't created any course bots yet.")