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
st.title("🎓 Student Learning Portal")
st.write("Welcome to the open course assistant.")

# (Your ChromaDB Client and Chat Logic go here)