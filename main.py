import streamlit as st
import streamlit_authenticator as stauth
import yaml
import chromadb
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
from weaviate.classes.init import Auth
from weaviate.classes.query import Filter

# --- WEAVIATE CONNECTION ---
# Using the same secrets you set up earlier
wcd_url = st.secrets["WEAVIATE_URL"]
wcd_api_key = st.secrets["WEAVIATE_API_KEY"]

@st.cache_resource # Keeps the connection alive without reconnecting every click
def get_weaviate_client():
    return weaviate.connect_to_weaviate_cloud(
        cluster_url=wcd_url,
        auth_credentials=Auth.api_key(wcd_api_key),
        headers={
        "X-Mistral-Api-Key": st.secrets["MISTRAL_KEY"] 
    }
    )

client = get_weaviate_client()
collection = client.collections.get("CourseBotMemory")

# --- STUDENT INTERFACE ---
st.title("🎓 Student Learning Portal")
st.write("Select your course to begin chatting with the course-specific knowledge base.")

# 1. Fetch all available courses across the institution
# We fetch them uniquely so students can pick from a list
all_objects = collection.query.fetch_objects(return_properties=["course_name"], limit=1000)
available_courses = sorted(list(set([obj.properties['course_name'] for obj in all_objects.objects])))

if available_courses:
    selected_course = st.selectbox("Choose a Course Bot:", available_courses)
    
    st.divider()
    
    # 2. Simple Chat Interface
    user_query = st.chat_input(f"Ask a question about {selected_course}...")
    
if user_query:
    with st.chat_message("user"):
        st.markdown(user_query)

    with st.chat_message("assistant"):
        # 1. Fetch data with Generative RAG
        # We use a 'single_prompt' to have the LLM answer based on the chunks
        response = collection.generate.hybrid(
            query=user_query,
            target_vector="default", # Ensure this matches your named vector if used
            filters=wvc.query.Filter.by_property("course_name").equal(selected_course),
            single_prompt=f"Answer the user query: '{user_query}' using only the provided context. "
                          "Use [citation n] format for every fact you mention.",
            limit=3
        )

        if response.objects:
            # 2. Extract the answer and sources
            full_answer = response.generated
            references = []
            
            for i, obj in enumerate(response.objects, 1):
                ref_name = obj.properties.get("doc_title", "Unknown Source")
                references.append(f"[citation {i}] - {ref_name}")

            # 3. The "F.R.I.D.A.Y." Streaming Effect
            placeholder = st.empty()
            streamed_text = ""
            
            # Simple word-by-word streaming for the typewriter feel
            for word in full_answer.split(" "):
                streamed_text += word + " "
                placeholder.markdown(streamed_text + "▌")
                time.sleep(0.05)
            
            # 4. Final render with the citation list
            ref_footer = "\n\n**References used:**\n" + "\n".join(references)
            placeholder.markdown(streamed_text + ref_footer)
            
        else:
            st.warning(f"Im not picking up anything relevant in those course files, {st.session_state['name']}.")