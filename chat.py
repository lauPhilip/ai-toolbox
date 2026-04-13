import streamlit as st
import weaviate
import time
import weaviate.classes as wvc
from weaviate.classes.init import Auth, AdditionalConfig, Timeout
from weaviate.classes.query import Filter
from datetime import datetime, timezone
from mistralai.client import Mistral

# --- 1. IDENTITY & GUEST GATEKEEPER ---
is_logged_in = st.session_state.get("authentication_status") is True
user_role = str(st.session_state.get("role")).lower() if st.session_state.get("role") else "guest"
raw_courses = st.session_state.get("course_ids", "")

# Standardizing the course list for filtering
if isinstance(raw_courses, str):
    my_course_list = [c.strip() for c in raw_courses.split(",") if c.strip()]
else:
    my_course_list = raw_courses if raw_courses else []

# Demo Throttling for unauthenticated users
if not is_logged_in:
    if "demo_count" not in st.session_state:
        st.session_state.demo_count = 0
    
    queries_left = 2 - st.session_state.demo_count
    if queries_left <= 0:
        st.error("🛑 Demo Limit Reached. Please Login to continue your research.")
        if st.button("Go to Login Gateway"):
            st.switch_page("pages/login.py")
        st.stop()
    else:
        st.warning(f"🕵️ Guest Mode: {queries_left} demo queries remaining.")

# --- 2. INITIALIZATION ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "active_bot" not in st.session_state:
    st.session_state.active_bot = None

# --- 3. TACTICAL HANDOFF LOGIC (NEW) ---
# Retrieve pre-selected bot DNA from the Student Hub
pre_course = st.session_state.get("preselected_course")
pre_bot = st.session_state.get("preselected_bot")

# --- 4. MAIN UI & CLIENTS ---
st.title("🎓 Chat")

col_clear_1, col_clear_2 = st.columns([8, 2])
with col_clear_2:
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

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
        pass

# --- 5. TACTICAL FILTERING & GUARDRAILS ---
fetch_filter = None
skip_query = False

# Student specific filter logic
if is_logged_in and user_role == "student":
    if not my_course_list:
        skip_query = True
    else:
        fetch_filter = Filter.by_property("course_id").contains_any(my_course_list)

# STOP: Guardrail for students with no assigned courses
if skip_query:
    st.info("👋 Welcome to AU Herning. Your account is active, but your clearance level hasn't been linked to a specific course yet. Please contact your instructor to unlock your materials.")
    st.stop()

# --- 6. DATA RETRIEVAL ---
try:
    course_objs = collection.query.fetch_objects(
        filters=fetch_filter,
        return_properties=["course_name"], 
        limit=1000
    )
    available_courses = sorted(list(set([obj.properties['course_name'] for obj in course_objs.objects])))
except Exception as e:
    available_courses = []
    st.error(f"Vault Communication Error. (Technical: {e})")

# --- 7. SELECTION & INTERACTION ---
if available_courses:
    c_col, b_col = st.columns(2)
    with c_col:
        # Check if we have a pre-selected course index
        c_idx = available_courses.index(pre_course) if pre_course in available_courses else 0
        selected_course = st.selectbox("🎯 Select Course:", available_courses, index=c_idx)
    
    bot_objs = collection.query.fetch_objects(
        filters=Filter.by_property("course_name").equal(selected_course),
        return_properties=["bot_name"],
        limit=1000
    )
    available_bots = sorted(list(set([obj.properties.get('bot_name', 'Standard Bot') for obj in bot_objs.objects])))
    
    with b_col:
        # Check if we have a pre-selected bot index
        b_idx = available_bots.index(pre_bot) if pre_bot in available_bots else 0
        selected_bot = st.selectbox("🤖 Select Course-bot:", available_bots, index=b_idx)
    
    # MISSION COMPLETE: Clear pre-selection so manual changes are possible afterwards
    if pre_course or pre_bot:
        st.session_state["preselected_course"] = None
        st.session_state["preselected_bot"] = None

    if st.session_state.active_bot != f"{selected_course}_{selected_bot}":
        st.session_state.messages = []
        st.session_state.active_bot = f"{selected_course}_{selected_bot}"

    st.divider()

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_query = st.chat_input(f"Chatting with {selected_bot}...")
    
    if user_query:
        if not is_logged_in:
            st.session_state.demo_count += 1
            
        st.session_state.messages.append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)

        with st.chat_message("assistant"):
            with st.spinner(f"{selected_bot} is scanning the course database..."):
                search_results = collection.query.hybrid(
                    query=user_query,
                    filters=Filter.by_property("course_name").equal(selected_course) & 
                            Filter.by_property("bot_name").equal(selected_bot),
                    return_properties=["chunk", "doc_title", "system_prompt", "temperature"],
                    limit=4
                )

            if search_results.objects:
                context_text = "\n".join([f"Source: {o.properties['doc_title']}\n{o.properties['chunk']}" for o in search_results.objects])
                teacher_prompt = search_results.objects[0].properties.get('system_prompt') or "You are a professional assistant."
                
                guardrail_prompt = f"""
                PRIMARY DIRECTIVE: {teacher_prompt}
                STRICT CONSTRAINTS:
                1. Use ONLY the provided context to answer. 
                2. If the answer is not in context, state that you do not know based on course materials.
                3. Maintain a professional academic tone.
                4. Do not offer information outside the scope of {selected_course}.
                """

                try:
                    response = mistral_client.chat.complete(
                        model="mistral-medium-latest",
                        temperature=float(search_results.objects[0].properties.get('temperature', 0.2)),
                        messages=[
                            {"role": "system", "content": guardrail_prompt},
                            {"role": "user", "content": f"CONTEXT:\n{context_text}\n\nQUESTION: {user_query}"}
                        ]
                    )
                    full_answer = response.choices[0].message.content
                    
                    placeholder = st.empty()
                    streamed_text = ""
                    for word in full_answer.split(" "):
                        streamed_text += word + " "
                        placeholder.markdown(streamed_text + "|")
                        time.sleep(0.01)
                    
                    refs = sorted(list(set([obj.properties['doc_title'] for obj in search_results.objects])))
                    footer = "\n\n**📚 References:** " + ", ".join([f"`{r}`" for r in refs])
                    final_content = streamed_text.strip() + footer
                    
                    placeholder.markdown(final_content)
                    st.session_state.messages.append({"role": "assistant", "content": final_content})
                    log_interaction(selected_course, selected_bot, user_query, full_answer)
                except Exception as e:
                    st.error(f"Intelligence Failure: {e}")
            else:
                st.warning("No relevant documentation found for this query.")
else:
    st.info("The AU Vault is currently empty for your track. Please wait for staff to deploy course materials.")