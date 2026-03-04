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
st.write(f"Debug: Status={st.session_state.get('authentication_status')}, Role={st.session_state.get('role')}")

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

st.title(f"👨‍🏫 {st.session_state['name']}'s Command Center")

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
tab_manage, tab_upload = st.tabs(["📚 My Course Bots", "➕ Create / Add Content"])

with tab_upload:
    st.subheader("Upload to Weaviate")
    course_name = st.text_input("Course Name (e.g., Engineering 101)")
    program_level = st.selectbox("Level", ["Bachelor", "Master"])
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
                                "program": program_level
                            }
                        )
            st.success(f"Successfully added {len(uploaded_files)} files to {course_name}!")
        else:
            st.warning("Course Name and Files are required.")

with tab_manage:
    # --- tab_manage section ---
    st.subheader("Your Active Courses")

    # Fetch unique courses managed by this specific teacher
    results = collection.query.fetch_objects(
        filters=Filter.by_property("course_administrator").equal(st.session_state['username']),
        return_properties=["course_name"],
        limit=1000 # Good practice to set a limit
    )

    # Get unique list of courses
    my_courses = list(set([obj.properties['course_name'] for obj in results.objects]))
    
    if my_courses:
        selected_course = st.selectbox("Select Course to Manage", my_courses)
        
        # Show files in this course
        file_results = collection.query.fetch_objects(
            filters=Filter.by_property("course_name").equal(selected_course),
            return_properties=["doc_title"],
            limit=1000
        )
        unique_files = list(set([obj.properties['doc_title'] for obj in file_results.objects]))
        
        st.write(f"Files in **{selected_course}**:")
        for f in unique_files:
            col1, col2 = st.columns([0.8, 0.2])
            col1.text(f"📄 {f}")
            if col2.button("🗑️", key=f"del_{f}"):
                # Delete all chunks associated with this specific file
                collection.data.delete_many(
                    where=wvc.query.Filter.by_property("doc_title").equal(f) &
                          wvc.query.Filter.by_property("course_name").equal(selected_course)
                )
                st.rerun()
    else:
        st.info("You haven't created any course bots yet.")