import streamlit as st
import weaviate
import time
import weaviate.classes as wvc
from weaviate.classes.init import Auth, AdditionalConfig, Timeout
from weaviate.classes.query import Filter
from datetime import datetime, timezone
from mistralai.client import Mistral

# --- 1. HARDENED INITIALIZATION ---
@st.cache_resource 
def get_weaviate_client():
    return weaviate.connect_to_weaviate_cloud(
        cluster_url=st.secrets["WEAVIATE_URL"],
        auth_credentials=Auth.api_key(st.secrets["WEAVIATE_API_KEY"]),
        headers={"X-Mistral-Api-Key": st.secrets["MISTRAL_KEY"]},
        additional_config=AdditionalConfig(
            timeout=Timeout(query=120, connect=120, init=120)
        )
    )

client = get_weaviate_client()
mistral_client = Mistral(api_key=st.secrets["MISTRAL_KEY"])

# --- 2. THE CHAT INTERFACE ---
st.title("🎓 Chat")
st.caption("Target Course: **Technological Business Model Innovation (480142U066)**")

# Define our target bot directly
TARGET_COURSE = "Technological Business Model Innovation (480142U066)"
# We default to a standard bot name; if you have a specific name, update it here.
TARGET_BOT = "Standard Bot" 

if "messages" not in st.session_state:
    st.session_state.messages = []

# Clear chat logic
if st.sidebar.button("🗑️ Clear Chat"):
    st.session_state.messages = []
    st.rerun()

# Display Chat History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 3. THE CHAT LOOP ---
user_query = st.chat_input(f"Analyzing Business Models...")

if user_query:
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    with st.chat_message("assistant"):
        with st.spinner(f"L.U.M.A. is auditing the vault for {TARGET_COURSE}..."):
            collection = client.collections.get("CourseBotMemory")
            try:
                # Execution: Direct filtering by the hardcoded course name
                search_results = collection.query.hybrid(
                    query=user_query,
                    filters=Filter.by_property("course_name").equal(TARGET_COURSE),
                    return_properties=["chunk", "doc_title", "system_prompt", "temperature"],
                    limit=5,
                    alpha=0.5
                )

                if search_results.objects:
                    context_text = "\n".join([f"Source: {o.properties['doc_title']}\n{o.properties['chunk']}" for o in search_results.objects])
                    
                    # Logic to get the teacher's specific prompt if available
                    teacher_prompt = search_results.objects[0].properties.get('system_prompt') or "You are an expert in Business Model Innovation."
                    
                    guardrail_prompt = f"""
                    SYSTEM INSTRUCTIONS: {teacher_prompt}
                    STRICT CONSTRAINT: ONLY use the provided course materials to answer. 
                    If the data is missing, state: 'This detail is not covered in the BMI Vault.'
                    """

                    response = mistral_client.chat.complete(
                        model="mistral-medium-latest",
                        temperature=0.2,
                        messages=[
                            {"role": "system", "content": guardrail_prompt},
                            {"role": "user", "content": f"CONTEXT:\n{context_text}\n\nQUESTION: {user_query}"}
                        ]
                    )
                    
                    full_answer = response.choices[0].message.content
                    
                    # Streaming effect
                    placeholder = st.empty()
                    streamed_text = ""
                    for word in full_answer.split(" "):
                        streamed_text += word + " "
                        placeholder.markdown(streamed_text + "|")
                        time.sleep(0.01)
                    
                    # Reference Footer
                    refs = sorted(list(set([obj.properties['doc_title'] for obj in search_results.objects])))
                    footer = "\n\n**📚 References:** " + ", ".join([f"`{r}`" for r in refs])
                    final_content = streamed_text.strip() + footer
                    
                    placeholder.markdown(final_content)
                    st.session_state.messages.append({"role": "assistant", "content": final_content})
                else:
                    st.warning(f"The Vault currently contains no relevant data for the course: {TARGET_COURSE}")
                    
            except Exception as e:
                if "timeout" in str(e).lower():
                    st.error("⏳ Vault Timeout: The database connection is slow. Please re-send your query.")
                else:
                    st.error(f"Intelligence Failure: {e}")