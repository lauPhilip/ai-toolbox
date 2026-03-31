import streamlit as st
import weaviate
import time
import weaviate.classes as wvc
from weaviate.classes.init import Auth, AdditionalConfig, Timeout
from weaviate.classes.query import Filter
from datetime import datetime, timezone
from mistralai.client import Mistral

# --- INITIALIZATION ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "active_bot" not in st.session_state:
    st.session_state.active_bot = None

# --- MAIN UI ---
st.title("🎓 Chat")

# Clear Chat logic
col1, col2 = st.columns([8, 2])
with col2:
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# --- CLIENTS ---
@st.cache_resource 
def get_weaviate_client():
    return weaviate.connect_to_weaviate_cloud(
        cluster_url=st.secrets["WEAVIATE_URL"],
        auth_credentials=Auth.api_key(st.secrets["WEAVIATE_API_KEY"]),
        headers={"X-Mistral-Api-Key": st.secrets["MISTRAL_KEY"]},
        additional_config=AdditionalConfig(timeout=Timeout(query=60))
    )

client = get_weaviate_client()
mistral_client = Mistral(api_key=st.secrets["MISTRAL_KEY"])
collection = client.collections.get("CourseBotMemory")

# --- UTILITY: LOGGING ---
def log_interaction(course, bot, query, response):
    try:
        log_collection = client.collections.get("InteractionLogs")
        log_collection.data.insert({
            "course_name": course,
            "bot_name": bot,
            "user_query": query,
            "ai_response": response,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    except:
        pass # Silent fail for logging to keep UX smooth

# --- STEP 1: HIERARCHICAL SELECTION ---
# Fetch all unique courses
course_objs = collection.query.fetch_objects(return_properties=["course_name"], limit=1000)
available_courses = sorted(list(set([obj.properties['course_name'] for obj in course_objs.objects])))

if available_courses:
    c_col, b_col = st.columns(2)
    with c_col:
        selected_course = st.selectbox("🎯 Select Course:", available_courses)
    
    # Fetch unique bots for the selected course
    bot_objs = collection.query.fetch_objects(
        filters=Filter.by_property("course_name").equal(selected_course),
        return_properties=["bot_name"],
        limit=1000
    )
    available_bots = sorted(list(set([obj.properties.get('bot_name', 'Standard Bot') for obj in bot_objs.objects])))
    
    with b_col:
        selected_bot = st.selectbox("🤖 Select Course-bot:", available_bots)
    
    # Reset chat if bot changes
    if st.session_state.active_bot != f"{selected_course}_{selected_bot}":
        st.session_state.messages = []
        st.session_state.active_bot = f"{selected_course}_{selected_bot}"

    st.divider()

    # --- CHAT INTERFACE ---
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_query = st.chat_input(f"Chatting with {selected_bot}...")
    
    if user_query:
        st.session_state.messages.append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)

        with st.chat_message("assistant"):
            with st.spinner(f"{selected_bot} is scanning documents..."):
                # Hybrid Search filtered by Course AND specific Bot
                search_results = collection.query.hybrid(
                    query=user_query,
                    filters=Filter.by_property("course_name").equal(selected_course) & 
                            Filter.by_property("bot_name").equal(selected_bot),
                    return_properties=["chunk", "doc_title", "system_prompt", "temperature"],
                    limit=4
                )

            if search_results.objects:
                context_text = "\n".join([f"Source: {o.properties['doc_title']}\n{o.properties['chunk']}" for o in search_results.objects])
                
                # --- PROMPT GUARDRAILS ---
                # We blend the teacher's prompt with strict primary directives
                teacher_prompt = search_results.objects[0].properties.get('system_prompt') or "You are a helpful assistant."
                
                guardrail_prompt = f"""
                PRIMARY DIRECTIVE: {teacher_prompt}
                
                STRICT CONSTRAINTS:
                1. Use ONLY the provided context to answer. 
                2. If the answer is not in the context, state that you do not know based on the course materials.
                3. Do not mention the context or 'Sources' directly in your prose unless asked.
                4. Maintain a professional, academic tone suitable for Aarhus University students.
                5. If the user asks for anything unethical or outside the scope of {selected_course}, politely decline.
                """

                try:
                    response = mistral_client.chat.complete(
                        model="mistral-medium-latest",
                        temperature=float(search_results.objects[0].properties.get('temperature', 0.2)),
                        messages=[
                            {"role": "system", "content": guardrail_prompt},
                            {"role": "user", "content": f"CONTEXT FROM COURSE DATABASE:\n{context_text}\n\nSTUDENT QUESTION: {user_query}"}
                        ]
                    )
                    full_answer = response.choices[0].message.content
                    
                    # Streaming effect
                    placeholder = st.empty()
                    streamed_text = ""
                    for word in full_answer.split(" "):
                        streamed_text += word + " "
                        placeholder.markdown(streamed_text + "▌")
                        time.sleep(0.02)
                    
                    # References footer
                    refs = sorted(list(set([obj.properties['doc_title'] for obj in search_results.objects])))
                    footer = "\n\n**📚 Sources:** " + ", ".join([f"`{r}`" for r in refs])
                    final_content = streamed_text.strip() + footer
                    
                    placeholder.markdown(final_content)
                    st.session_state.messages.append({"role": "assistant", "content": final_content})
                    log_interaction(selected_course, selected_bot, user_query, full_answer)

                except Exception as e:
                    st.error(f"Intelligence Failure: {e}")
            else:
                st.warning("I couldn't find any relevant data in the course files for that specific query.")

else:
    st.info("The AU Registry is currently empty. Please wait for staff to upload course bots.")