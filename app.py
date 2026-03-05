import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

st.set_page_config(page_title="au-btech-course-bot", layout="wide")

# 1. Load the user database
with open('config.yaml', 'r') as file:
    config = yaml.load(file, Loader=SafeLoader)

# 2. Initialize Authenticator
# Moving this here ensures it only initializes ONCE
authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

# --- 3. PAGE DEFINITIONS ---
# We define the pages. 'main.py' is renamed to 'student_portal.py' to avoid confusion
student_portal = st.Page("student_portal.py", title="Student Portal", icon="🎓", default=True)
teacher_dashboard = st.Page("pages/1_👨‍🏫_Teacher.py", title="Teacher Dashboard", icon="👨‍🏫")
analytics_page = st.Page("pages/2_📊_Analytics.py", title="Analytics", icon="📊")

# --- 4. NAVIGATION LOGIC ---
if st.session_state.get("authentication_status"):
    # Show both when logged in
    pg = st.navigation({"Portal": [student_portal], "Staff": [teacher_dashboard, analytics_page]})
else:
    # Hide Teacher Dashboard when logged out
    pg = st.navigation({"Portal": [student_portal]})

# --- 5. SIDEBAR AUTH UI ---
with st.sidebar:
    st.title("👨‍🏫 Staff Access")
    
    # Check if we are NOT logged in
    if not st.session_state.get("authentication_status"):
        choice = st.radio("Select Action", ["Log In", "Sign Up"], horizontal=True, label_visibility="collapsed")
        
        if choice == "Log In":
            # 1. Trigger the login form
            authenticator.login(location='sidebar', key='main_login')
            
            # 2. If the status JUST flipped to True, sync the role
            if st.session_state.get("authentication_status"):
                username = st.session_state.get("username")
                
                # Look up the role in the config loaded from config.yaml
                user_role = config['credentials']['usernames'][username].get('role')
                
                # Store it in session state so other pages can see it
                st.session_state['role'] = user_role
                
                # 3. Rerun to update navigation and page content
                st.rerun() 
                
        else: # Sign Up Choice
            try:
                if authenticator.register_user(location='sidebar', domains=['btech.au.dk'], roles=['teacher']):
                    with open('config.yaml', 'w') as file:
                        yaml.dump(config, file, default_flow_style=False)
                    st.success('Success! Please Log In.')
            except Exception as e:
                st.error(f"Error: {e}")
                
    else:
        # User is already logged in
        st.write(f"Welcome, **{st.session_state['name']}**")
        
        # Display the role (Optional, but helpful for debugging)
        if st.session_state.get('role'):
            st.caption(f"Status: Authorized {st.session_state['role'].capitalize()}")
            
        st.divider()
        
        # Logout logic
        authenticator.logout('Log out', 'sidebar')
        
        # Safety: If they just logged out, clear the role from memory
        if not st.session_state.get("authentication_status"):
            st.session_state['role'] = None
            st.rerun()

# Render the active page
pg.run()