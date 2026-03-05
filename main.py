import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

st.set_page_config(page_title="au-btech-course-bot", layout="wide")

# 1. Load the user database
with open('config.yaml', 'r') as file:
    config = yaml.load(file, Loader=SafeLoader)

# 2. Initialize Authenticator
authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

# --- SIDEBAR: STAFF GATEWAY ---
with st.sidebar:
    st.title("👨‍🏫 Staff Access")
    
    if not st.session_state.get("authentication_status"):
        # We use a radio or tabs to strictly separate the forms
        choice = st.radio("Select Action", ["Log In", "Sign Up"], horizontal=True, label_visibility="collapsed")
        
        if choice == "Log In":
            # v0.3.0+ returns (name, status, username). We don't unpack 'role' here.
            result = authenticator.login(location='sidebar', key='main_login')
            
            # Use direct session state check which is more reliable across pages
            if st.session_state.get("authentication_status"):
                username = st.session_state.get("username")
                
                # 1. Force-sync the role from your YAML config
                user_role = config['credentials']['usernames'][username].get('role')
                st.session_state['role'] = user_role
                
                # 2. Immediate Redirect
                if user_role == 'teacher':
                    st.switch_page("pages/1_👨‍🏫_Teacher.py")
                else:
                    st.rerun()
                    
            elif st.session_state.get("authentication_status") is False:
                st.error("Invalid @btech.au.dk credentials.")
                    
        else: # Sign Up Choice
            try:
                # This only shows when the user selects 'Sign Up'
                if authenticator.register_user(location='sidebar', domains=['btech.au.dk'], roles=['teacher']):
                    with open('config.yaml', 'w') as file:
                        yaml.dump(config, file, default_flow_style=False)
                    st.success('Success! Please switch to Log In.')
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.write(f"Welcome, **{st.session_state['name']}**")
        if st.button("🚀 Open Teacher Dashboard", use_container_width=True):
            st.switch_page("pages/1_👨‍🏫_Teacher.py")
        st.divider()
        authenticator.logout('Log out', 'sidebar')

# --- MAIN PAGE: OPEN STUDENT PORTAL ---
import streamlit as st
import weaviate
import time
import weaviate.classes as wvc
from weaviate.classes.init import Auth, AdditionalConfig, Timeout
from mistralai import Mistral

# --- 1. MISTRAL & WEAVIATE CLIENT SETUP ---
mistral_client = Mistral(api_key=st.secrets["MISTRAL_KEY"])

@st.cache_resource 
def get_weaviate_client():
    return weaviate.connect_to_weaviate_cloud(
        cluster_url=st.secrets["WEAVIATE_URL"],
        auth_credentials=Auth.api_key(st.secrets["WEAVIATE_API_KEY"]),
        # We keep the timeout config for the hybrid search part
        additional_config=AdditionalConfig(
            timeout=Timeout(query=60, insert=120, init=30) 
        )
    )

client = get_weaviate_client()
collection = client.collections.get("CourseBotMemory")

# --- 2. STUDENT INTERFACE ---
st.title("🎓 Student Learning Portal")
st.write("Select your course to begin chatting with the course-specific knowledge base.")

# Fetch available courses
all_objects = collection.query.fetch_objects(return_properties=["course_name"], limit=1000)
available_courses = sorted(list(set([obj.properties['course_name'] for obj in all_objects.objects])))

if available_courses:
    selected_course = st.selectbox("Choose a Course Bot:", available_courses)
    st.divider()
    user_query = st.chat_input(f"Ask a question about {selected_course}...")
    
    if user_query:
        # User message
        with st.chat_message("user"):
            st.markdown(user_query)

        # Assistant message
        with st.chat_message("assistant"):
            # STEP A: Retrieve chunks from Weaviate (Standard Search)
            with st.spinner("Searching course materials..."):
                search_results = collection.query.hybrid(
                    query=user_query,
                    filters=wvc.query.Filter.by_property("course_name").equal(selected_course),
                    limit=3
                )

            if search_results.objects:
                # STEP B: Format Context for Mistral
                context_text = ""
                references = []
                for i, obj in enumerate(search_results.objects, 1):
                    # We pull the actual chunk text and the doc title
                    chunk_content = obj.properties.get('chunk', 'No content found.')
                    doc_title = obj.properties.get('doc_title', 'Unknown Source')
                    
                    context_text += f"---\nSource {i}:\n{chunk_content}\n"
                    references.append(f"[citation {i}] - {doc_title}")

                # STEP C: Generate response using Mistral SDK
                with st.spinner("Mistral is analyzing and writing..."):
                    try:
                        chat_response = mistral_client.chat.complete(
                            model="mistral-medium-latest",
                            messages=[
                                {
                                    "role": "system", 
                                    "content": ("You are a professional academic assistant. "
                                               "Answer based ONLY on the provided context. "
                                               "If the answer isn't in the context, say you don't know. "
                                               "Use [citation n] format for every fact mentioned.")
                                },
                                {
                                    "role": "user", 
                                    "content": f"Context:\n{context_text}\n\nQuestion: {user_query}"
                                },
                            ]
                        )
                        full_answer = chat_response.choices[0].message.content
                    except Exception as e:
                        st.error(f"Mistral API Error: {e}")
                        st.stop()

                # STEP D: Streaming Effect
                placeholder = st.empty()
                streamed_text = ""
                
                # Split by words for the typewriter feel
                for word in full_answer.split(" "):
                    streamed_text += word + " "
                    placeholder.markdown(streamed_text + "▌")
                    time.sleep(0.04)
                
                # Final render with Reference Footer
                ref_footer = "\n\n**References used:**\n" + "\n".join(references)
                placeholder.markdown(streamed_text.strip() + ref_footer)
                
            else:
                st.warning(f"No relevant information found for '{selected_course}' in the database.")
else:
    st.info("No course materials have been uploaded yet.")