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

if isinstance(raw_courses, str):
    my_course_list = [c.strip() for c in raw_courses.split(",") if c.strip()]
else:
    my_course_list = raw_courses if raw_courses else []

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

pre_course = st.session_state.get("preselected_course")
pre_bot = st.session_state.get("preselected_bot")

# --- 3. UI & HARDENED CLIENTS ---
st.title("🎓 Chat")

col_clear_1, col_clear_2 = st.columns([8, 2])
with col_clear_2:
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

@st.cache_resource 
def get_weaviate_client():
    # HARDENED TIMEOUTS: query=120, connect=120, init=120
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

# --- 4. TACTICAL FILTERING ---
fetch_filter = None
skip_query = False

if is_logged_in and user_role == "student":
    if not my_course_list:
        skip_query = True
    else:
        fetch_filter = Filter.by_property("course_id").contains_any(my_course_list)

if skip_query:
    st.info("👋 Welcome to AU Herning. Clearances pending. Contact instructor.")
    st.stop()

# --- 5. DATA RETRIEVAL (Lightweight) ---
try:
    course_objs = collection.query.fetch_objects(
        filters=fetch_filter,
        return_properties=["course_name"], 
        limit=50 # Reduced from 1000 to prevent initial load timeout
    )
    available_courses = sorted(list(set([obj.properties['course_name'] for obj in course_objs.objects])))
except Exception as e:
    available_courses = []
    st.error(f"Vault Latency Error. (Technical: {e})")

# --- 6. SELECTION & CHAT ---
if available_courses:
    c_col, b_col = st.columns(2)
    with c_col:
        c_idx = available_courses.index(pre_course) if pre_course in available_courses else 0
        selected_course = st.selectbox("🎯 Select Course:", available_courses, index=c_idx)
    
    bot_objs = collection.query.fetch_objects(
        filters=Filter.by_property("course_name").equal(selected_course),
        return_properties=["bot_name"],
        limit=50
    )
    available_bots = sorted(list(set([obj.properties.get('bot_name', 'Standard Bot') for obj in bot_objs.objects])))
    
    with b_col:
        b_idx = available_bots.index(pre_bot) if pre_bot in available_bots else 0
        selected_bot = st.selectbox("🤖 Select Course-bot:", available_bots, index=b_idx)
    
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
            with st.spinner(f"searching"):
                try:
                    # Hybrid search with explicit 0.5 alpha for speed-stability balance
                    search_results = collection.query.hybrid(
                        query=user_query,
                        filters=Filter.by_property("course_name").equal(selected_course) & 
                                Filter.by_property("bot_name").equal(selected_bot),
                        return_properties=["chunk", "doc_title", "system_prompt", "temperature"],
                        limit=4,
                        alpha=0.5
                    )

                    if search_results.objects:
                        context_text = "\n".join([f"Source: {o.properties['doc_title']}\n{o.properties['chunk']}" for o in search_results.objects])
                        teacher_prompt = search_results.objects[0].properties.get('system_prompt') or "You are a professional assistant."
                        
                        guardrail_prompt = f"DIRECTIVE: {teacher_prompt}\nSTRICTLY use ONLY provided context."

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
                    else:
                        st.warning("No relevant documentation found.")
                except Exception as e:
                    if "timeout" in str(e).lower():
                        st.error("⏳ Intelligence Timeout: The cloud vault is taking too long to respond. Please try again.")
                    else:
                        st.error(f"Intelligence Failure: {e}")
else:
    st.info("The AU Vault is currently empty for your track.")