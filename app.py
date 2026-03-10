import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import os

st.set_page_config(page_title="au-btech-course-bot", layout="wide")

# We check if they exist; if not, we create them
if "config" not in st.session_state:
    if os.path.exists('config.yaml'):
        with open('config.yaml', 'r') as file:
            # Safely handle empty files
            loaded_config = yaml.load(file, Loader=SafeLoader)
            st.session_state["config"] = loaded_config if loaded_config else {}
    else:
        st.session_state["config"] = {"credentials": {"usernames": {}}}

# Now that we KNOW "config" exists, we can safely subscript it
config = st.session_state["config"]

# Provide defaults if the YAML was missing keys to prevent KeyErrors
authenticator = stauth.Authenticate(
    config.get('credentials', {'usernames': {}}),
    config.get('cookie', {}).get('name', 'au_auth'),
    config.get('cookie', {}).get('key', 'signature_key'), 
    config.get('cookie', {}).get('expiry_days', 30)
)

st.session_state["authenticator"] = authenticator

# --- 2. PAGE DEFINITIONS ---
landing_page = st.Page("landing.py", title="Home", icon="🏠", default=True)
student_portal = st.Page("student_portal.py", title="Student Portal", icon="🎓")
student_prompt_lib = st.Page("pages/4_📋_Student_Prompt_Library.py", title="Prompt Library", icon="📋")
auth_page = st.Page("pages/auth.py", title="Staff Access", icon="🔑")

# Staff Only Pages
teacher_dashboard = st.Page("pages/1_👨‍🏫_Teacher.py", title="Teacher Dashboard", icon="👨‍🏫")
analytics_page = st.Page("pages/2_📊_Analytics.py", title="Analytics", icon="📊")
prompt_library = st.Page("pages/3_📚_System_Prompt_Library.py", title="System Prompt Library", icon="📚")

# --- 3. DYNAMIC NAVIGATION ---
auth_status = st.session_state.get("authentication_status")

if auth_status:
    # 1. LOGGED IN VIEW (Already categorized)
    role = str(st.session_state.get("role")).lower()
    if role == "teacher":
        pg = st.navigation({
            " Student Portal": [landing_page, student_portal, student_prompt_lib],
            " Staff Management": [teacher_dashboard, analytics_page, prompt_library]
        })
    else:
        pg = st.navigation({"🎓 Student Portal": [landing_page, student_portal, student_prompt_lib]})

else:
    # 2. LOGGED OUT VIEW (New Categorization)
    # This clearly separates the student world from the staff world
    pg = st.navigation({
        " Student Portal": [landing_page, student_portal, student_prompt_lib],
        " Teachers": [auth_page]})

# --- 4. SIDEBAR LOGOUT & BRANDING ---
with st.sidebar:
    
    if st.session_state.get("authentication_status"):
        st.write(f"Authorized: **{st.session_state['name']}**")
        
        # We grab the authenticator from the session state
        authenticator = st.session_state.get("authenticator")
        
        if st.button("🚪 Log Out", type="secondary", width='stretch'):
            # 1. Official Library Logout (Clears cookies/state)
            authenticator.logout(location='unrendered') 
            
            # 2. Manual state wipe for safety
            st.session_state["authentication_status"] = None
            st.session_state["username"] = None
            st.session_state["role"] = None
            
            # 3. Redirect to the 'Front Door'
            st.switch_page("landing.py")

pg.run()