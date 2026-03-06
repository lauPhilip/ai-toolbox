import streamlit as st
import weaviate
import time
import weaviate.classes as wvc
from weaviate.classes.init import Auth, AdditionalConfig, Timeout
from mistralai import Mistral

# Initialize session state for messages
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- MAIN PAGE: STUDENT INTERFACE ---
st.title("🎓 AU Herning Course-bot | Student Learning Portal")

# 1. Clear Chat UI
col1, col2 = st.columns([9, 1])
with col2:
    if st.button("🗑️ Clear Chat", width='stretch'):
        st.session_state.messages = []
        st.rerun()

st.write("Select your course to begin chatting with the course-specific knowledge base.")

# --- CLIENTS & LOGIC ---
mistral_client = Mistral(api_key=st.secrets["MISTRAL_KEY"])

@st.cache_resource 
def get_weaviate_client():
    return weaviate.connect_to_weaviate_cloud(
        cluster_url=st.secrets["WEAVIATE_URL"],
        auth_credentials=Auth.api_key(st.secrets["WEAVIATE_API_KEY"]),
        headers={"X-Mistral-Api-Key": st.secrets["MISTRAL_KEY"]},
        additional_config=AdditionalConfig(timeout=Timeout(query=60))
    )

client = get_weaviate_client()
collection = client.collections.get("CourseBotMemory")

#   For saving the input
from datetime import datetime, timezone

def log_interaction(course, query, response):
    try:
        log_collection = client.collections.get("InteractionLogs")
        
        # Convert current time to RFC3339 string (e.g., '2026-03-05T15:21:55Z')
        current_time_rfc3339 = datetime.now(timezone.utc).isoformat()
        
        log_collection.data.insert({
            "course_name": course,
            "user_query": query,
            "ai_response": response,
            "timestamp": current_time_rfc3339  # This now matches Weaviate's requirements
        })
    except Exception as e:
        st.error(f"Logging Error: {e}")

# Fetch available courses
all_objects = collection.query.fetch_objects(return_properties=["course_name"], limit=1000)
available_courses = sorted(list(set([obj.properties['course_name'] for obj in all_objects.objects])))

if available_courses:
    selected_course = st.selectbox("Choose a Course Bot:", available_courses)
    st.divider()

    # Display existing chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat Input
    user_query = st.chat_input(f"Ask a question about {selected_course}...")
    
    if user_query:
        st.session_state.messages.append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)

        with st.chat_message("assistant"):
            with st.spinner("Searching course materials..."):
                search_results = collection.query.hybrid(
                    query=user_query,
                    filters=wvc.query.Filter.by_property("course_name").equal(selected_course),
                    return_properties=["chunk", "doc_title", "system_prompt", "temperature"],
                    limit=3
                )

            if search_results.objects:
                context_text = ""
                references = []

                first_obj = search_results.objects[0]
                dynamic_sys_prompt = first_obj.properties.get('system_prompt') or "You are a professional academic assistant."
                dynamic_temp = first_obj.properties.get('temperature')
                # Ensure temperature is a float and within 0.0-1.0; default to 0.2 if missing
                final_temp = float(dynamic_temp) if dynamic_temp is not None else 0.2

                for i, obj in enumerate(search_results.objects, 1):
                    chunk_content = obj.properties.get('chunk', 'No content found.')
                    doc_title = obj.properties.get('doc_title', 'Unknown Source')
                    context_text += f"---\nSource {i}:\n{chunk_content}\n"
                    references.append(f"[{i}] - {doc_title}")

                with st.spinner("Mistral is analyzing and writing..."):
                    try:
                        chat_response = mistral_client.chat.complete(
                            model="mistral-medium-latest",
                            messages=[
                                {"role": "system", "content": dynamic_sys_prompt},
                                {"role": "user", "content": f"Context:\n{context_text}\n\nQuestion: {user_query}"},
                            ]
                        )
                        full_answer = chat_response.choices[0].message.content
                    except Exception as e:
                        st.error(f"Mistral API Error: {e}")
                        st.stop()

                placeholder = st.empty()
                streamed_text = ""
                for word in full_answer.split(" "):
                    streamed_text += word + " "
                    placeholder.markdown(streamed_text + "▌")
                    time.sleep(0.04)
                
                ref_footer = "\n\n**References used:**\n" + "\n".join(references)
                final_content = streamed_text.strip() + ref_footer
                placeholder.markdown(final_content)
                st.session_state.messages.append({"role": "assistant", "content": final_content})
                log_interaction(selected_course, user_query, final_content)
            else:
                st.warning(f"No relevant information found for '{selected_course}'.")
else:
    st.info("No course materials have been uploaded yet.")