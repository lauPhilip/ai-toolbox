import streamlit as st
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
import os

st.title("👨‍🏫 Staff Access Control")
st.divider()

# 1. Grab objects from session state
config = st.session_state["config"]
authenticator = st.session_state["authenticator"]

choice = st.radio("Select Action", ["Login", "Register"], horizontal=True)

if choice == "Login":
    # Login usually behaves better
    authenticator.login(location='main', key='page_login')
    if st.session_state.get("authentication_status"):
        username = st.session_state.get("username")
        user_info = config['credentials']['usernames'].get(username, {})
        st.session_state['role'] = user_info.get('role', 'teacher')
        st.success(f"Welcome back, {st.session_state['name']}!")
        st.rerun()

else:
    st.subheader("📝 Create Staff Account")
    # We use a container instead of a form to avoid the 'Nested Form' error
    with st.container(border=True):
        reg_name = st.text_input("Full Name (e.g., Philip Lau)")
        reg_email = st.text_input("Email (@btech.au.dk)")
        reg_username = st.text_input("Username")
        reg_password = st.text_input("Password", type="password")
        reg_password_repeat = st.text_input("Repeat Password", type="password")
        
    if st.button("🚀 Register Account", type="primary"):
        # 1. AUTHENTIC RELOAD: Get the freshest data from the disk first
        if os.path.exists('config.yaml'):
            with open('config.yaml', 'r') as file:
                current_config = yaml.load(file, Loader=SafeLoader) or {}
        else:
            current_config = {"credentials": {"usernames": {}}, "cookie": {}}

        # 2. NAVIGATE THE STRUCTURE: Ensure the keys exist before appending
        if 'credentials' not in current_config:
            current_config['credentials'] = {'usernames': {}}
        if 'usernames' not in current_config['credentials']:
            current_config['credentials']['usernames'] = {}

        # 3. VALIDATE: Check if the username already exists in the FILE
        if reg_username in current_config['credentials']['usernames']:
            st.error(f"User '{reg_username}' already exists in the AU BTECH database.")
        elif not reg_email.endswith("@btech.au.dk"):
            st.error("Access Denied: Use an official @btech.au.dk email.")
        else:
            # 4. HASH & APPEND: Use the new v0.3.0 hashing utility
            hashed_pw = stauth.Hasher.hash(reg_password)
            
            # Add the new user to the existing dictionary
            current_config['credentials']['usernames'][reg_username] = {
                "email": reg_email,
                "name": reg_name,
                "password": hashed_pw,
                "role": "teacher"
            }

            # 5. ATOMIC SAVE: Overwrite the file with the COMPLETE updated list
            with open('config.yaml', 'w') as file:
                yaml.dump(current_config, file, default_flow_style=False)
                
            # Update session state so the Login tab sees the new user immediately
            st.session_state["config"] = current_config
            
            st.success(f"Successfully registered {reg_name}. You can now log in.")
            st.balloons()