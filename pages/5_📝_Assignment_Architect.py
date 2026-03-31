import streamlit as st

st.title("📝 Assignment Architect")
st.markdown("##### Define mission parameters and grading rubrics for Herning students.")
st.divider()

# Role Guard (Security first)
if st.session_state.get("role") != "teacher":
    st.error("Access Denied. Internal Staff Credentials Required.")
    st.stop()

with st.container(border=True):
    st.subheader("Step 1: Assignment DNA")
    title = st.text_input("Assignment Title", placeholder="e.g., Business Engineering Report 101")
    
    col1, col2 = st.columns(2)
    with col1:
        description = st.text_area("Task Description", height=200, placeholder="What are the students building?")
    with col2:
        outcomes = st.text_area("Learning Outcomes", height=200, placeholder="1. Identify market trends\n2. Calculate ROI...")

with st.container(border=True):
    st.subheader("Step 2: The Answer Scheme (Hidden from Students)")
    st.info("This file will be used by the AI to grade student submissions internally.")
    answer_file = st.file_uploader("Upload Master Answer Scheme / Rubric (PDF)", type=['pdf'])

if st.button("Deploy Assignment to Course-bot", type="primary", width="stretch"):
    if title and outcomes and answer_file:
        # We will plug the Weaviate 'save' logic here in the next step
        st.success(f"Assignment '{title}' is now live in the system, Master Lau.")
    else:
        st.warning("Please complete all tactical fields before deployment.")