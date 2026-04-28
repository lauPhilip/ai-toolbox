import streamlit as st
import streamlit_authenticator as stauth
import weaviate
from weaviate.classes.init import Auth
import weaviate.classes.config as wvc
from weaviate.classes.query import Filter
import os

st.set_page_config(page_title="AU BTECH Course-Bot", layout="wide")

# --- 1. WEAVIATE CONNECTION & REGISTRY SETUP ---
@st.cache_resource
def get_weaviate_client():
    """Maintains a single stable connection to the cloud registry."""
    return weaviate.connect_to_weaviate_cloud(
        cluster_url=st.secrets["WEAVIATE_URL"],
        auth_credentials=Auth.api_key(st.secrets["WEAVIATE_API_KEY"]),
    )

# Exported client for use in sub-pages
client = get_weaviate_client()

def ensure_user_registry_exists():
    """Checks the cloud vault and creates/updates the UserRegistry if missing."""
    if not client.collections.exists("UserRegistry"):
        client.collections.create(
            name="UserRegistry",
            vectorizer_config=wvc.Configure.Vectorizer.none(),
            properties=[
                wvc.Property(name="username", data_type=wvc.DataType.TEXT),
                wvc.Property(name="password_hash", data_type=wvc.DataType.TEXT),
                wvc.Property(name="name", data_type=wvc.DataType.TEXT),
                wvc.Property(name="email", data_type=wvc.DataType.TEXT),
                wvc.Property(name="role", data_type=wvc.DataType.TEXT),
                wvc.Property(name="course_ids", data_type=wvc.DataType.TEXT), 
            ]
        )

ensure_user_registry_exists()

# --- 2. AUTHENTICATION HANDSHAKE ---
if "authenticator" not in st.session_state:
    authenticator = stauth.Authenticate(
        {'usernames': {}}, 
        st.secrets["COOKIE_NAME"],
        st.secrets["COOKIE_KEY"],
        30 
    )
    st.session_state["authenticator"] = authenticator

authenticator = st.session_state["authenticator"]

# --- 3. PAGE DEFINITIONS ---
landing_page = st.Page("landing.py", title="Home", icon="🏠", default=True)
chat_page = st.Page("chat.py", title="Chat", icon="🎓")
prompt_lib_student = st.Page("pages/4_📋_Student_Prompt_Library.py", title="Prompt Library", icon="📋")
login_page = st.Page("pages/login.py", title="Login", icon="🔐")

teacher_dashboard = st.Page("pages/1_👨‍🏫_Teacher.py", title="Teacher Dashboard", icon="👨‍🏫")
analytics_page = st.Page("pages/2_📊_Analytics.py", title="Analytics", icon="📊")
sys_prompt_library = st.Page("pages/3_📚_System_Prompt_Library.py", title="System Prompt Library", icon="📚")
assignment_architect = st.Page("pages/5_📝_Assignment_Architect.py", title="Assignment Architect", icon="📝")
course_registrar = st.Page("pages/6_🏫_Course_Registrar.py", title="Course Registrar", icon="🏫")
student_hub = st.Page("pages/7_📂_student_hub.py", title="Course Hub", icon="📂")
lit_review_agent = st.Page("pages/8_📚_LiteratureReviewAgent.py", title="Literature Review Agent", icon="🔬")

# --- 4. DYNAMIC NAVIGATION ENGINE ---
auth_status = st.session_state.get("authentication_status")

if auth_status:
    role = str(st.session_state.get("role")).lower()
    if role == "teacher":
        pg = st.navigation({
            "Student Portal": [landing_page, chat_page, prompt_lib_student, student_hub],
            "Staff Management": [teacher_dashboard, analytics_page, sys_prompt_library, assignment_architect, course_registrar],
            "Academia": [lit_review_agent],
        })
    else:
        pg = st.navigation({
            "My Learning": [landing_page, chat_page, prompt_lib_student, student_hub]
        })
else:
    pg = st.navigation({
        "Gateway": [landing_page, login_page],
        "Preview": [chat_page, prompt_lib_student]
    })

# --- 5. SIDEBAR BRANDING & LOGOUT ---
with st.sidebar:
    if auth_status:
        st.write(f"Authorized: **{st.session_state['name']}**")
        st.caption(f"Role: {st.session_state['role'].upper()}")
        
        if st.button("Log Out", type="secondary", use_container_width=True):
            st.session_state.update({
                "authentication_status": None,
                "username": None,
                "role": None,
                "name": None,
                "course_ids": None,
                "email": None
            })
            st.rerun()

pg.run()