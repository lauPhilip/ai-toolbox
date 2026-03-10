import streamlit as st
import streamlit_authenticator as stauth
import weaviate
from weaviate.classes.init import Auth
import weaviate.classes.config as wvc
from weaviate.classes.query import Filter
import os

st.set_page_config(page_title="au-btech-course-bot", layout="wide")

# --- 1. WEAVIATE CONNECTION & REGISTRY SETUP ---
@st.cache_resource
def get_weaviate_client():
    """Maintains a single stable connection to the cloud registry to avoid memory leaks."""
    return weaviate.connect_to_weaviate_cloud(
        cluster_url=st.secrets["WEAVIATE_URL"],
        auth_credentials=Auth.api_key(st.secrets["WEAVIATE_API_KEY"]),
    )

client = get_weaviate_client()

def ensure_user_registry_exists():
    """Checks the cloud vault and creates the UserRegistry if it is missing."""
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
            ]
        )

ensure_user_registry_exists()

# --- 2. AUTHENTICATION HANDSHAKE (Cloud-Based) ---
if "authenticator" not in st.session_state:
    # We pull the COOKIE keys from your updated secrets.toml
    authenticator = stauth.Authenticate(
        {'usernames': {}}, # Credentials are now verified via Weaviate queries in auth.py
        st.secrets["COOKIE_NAME"],
        st.secrets["COOKIE_KEY"],
        30 # Cookie expiry in days
    )
    st.session_state["authenticator"] = authenticator

authenticator = st.session_state["authenticator"]

# --- 3. PAGE DEFINITIONS ---
landing_page = st.Page("landing.py", title="Home", icon="🏠", default=True)
student_portal = st.Page("student_portal.py", title="Student Portal", icon="🎓")
student_prompt_lib = st.Page("pages/4_📋_Student_Prompt_Library.py", title="Prompt Library", icon="📋")
auth_page = st.Page("pages/auth.py", title="Staff Access", icon="🔑")

# Staff Management Cluster
teacher_dashboard = st.Page("pages/1_👨‍🏫_Teacher.py", title="Teacher Dashboard", icon="👨‍🏫")
analytics_page = st.Page("pages/2_📊_Analytics.py", title="Analytics", icon="📊")
prompt_library = st.Page("pages/3_📚_System_Prompt_Library.py", title="System Prompt Library", icon="📚")

# --- 4. DYNAMIC NAVIGATION ---
auth_status = st.session_state.get("authentication_status")

if auth_status:
    role = str(st.session_state.get("role")).lower()
    if role == "teacher":
        pg = st.navigation({
            "🎓 Student Portal": [landing_page, student_portal, student_prompt_lib],
            "🛠️ Staff Management": [teacher_dashboard, analytics_page, prompt_library]
        })
    else:
        pg = st.navigation({"🎓 Student Portal": [landing_page, student_portal, student_prompt_lib]})
else:
    # Categorized navigation for a clean BTECH student experience
    pg = st.navigation({
        "🎓 Student Portal": [landing_page, student_portal, student_prompt_lib],
        "🔑 Teachers": [auth_page]
    })

# --- 5. SIDEBAR BRANDING & LOGOUT ---
with st.sidebar:
    # Institutional Logo Header
    logo_col1, logo_col2 = st.columns(2)
    with logo_col1:
        st.image("img/AU-LOGO.png", width=None)
    with logo_col2:
        st.image("img/IT-VEST-LOGO.png", width=None)
    
    st.divider()
    
    if st.session_state.get("authentication_status"):
        st.write(f"Authorized: **{st.session_state['name']}**")
        
        # Logout logic using the 2026 'stretch' button syntax
        if st.button("🚪 Log Out", type="secondary", width='stretch'):
            authenticator.logout(location='unrendered') 
            st.session_state.update({
                "authentication_status": None,
                "username": None,
                "role": None,
                "name": None
            })
            st.switch_page(landing_page)

pg.run()