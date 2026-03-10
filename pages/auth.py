import streamlit as st
import streamlit_authenticator as stauth
from weaviate.classes.query import Filter
import time

st.title("👨‍🏫 Staff Access Control")
st.divider()

# 1. Grab the global Weaviate client and Authenticator from app.py
if "authenticator" not in st.session_state:
    st.error("course-bot. Connection Error. Please return to the Home page.")
    st.stop()

# Using the cached client established in app.py
client = st.session_state.get("weaviate_client") # Ensure this is set in app.py or use the getter
if not client:
    from app import get_weaviate_client
    client = get_weaviate_client()

authenticator = st.session_state["authenticator"]
user_registry = client.collections.get("UserRegistry")

choice = st.radio("Select Action", ["Login", "Register"], horizontal=True)

if choice == "Login":
    st.subheader("🔑 Staff Login")
    
    # We use custom login fields to verify against Weaviate directly
    with st.container(border=True):
        login_user = st.text_input("Username")
        login_pass = st.text_input("Password", type="password")
        
        if st.button("Log In", type="primary", width='stretch'):
            # Query Weaviate for the specific user
            response = user_registry.query.fetch_objects(
                filters=Filter.by_property("username").equal(login_user),
                limit=1
            )
            
            if response.objects:
                user_obj = response.objects[0].properties
                stored_hash = user_obj["password_hash"]
                
                # Verify the password using the stauth utility
                if stauth.Hasher.check_pw(stored_hash, login_pass):
                    st.session_state["authentication_status"] = True
                    st.session_state["username"] = login_user
                    st.session_state["name"] = user_obj["name"]
                    st.session_state["role"] = user_obj["role"]
                    
                    st.success(f"Welcome back, {user_obj['name']}!")
                    time.sleep(1)
                    st.switch_page("landing.py")
                else:
                    st.error("Incorrect password.")
            else:
                st.error("User not found in the AU BTECH registry.")

else:
    st.subheader("📝 Create Staff Account")
    with st.container(border=True):
        reg_name = st.text_input("Full Name (e.g., Philip Lau)")
        reg_email = st.text_input("Email (@btech.au.dk)")
        reg_username = st.text_input("Username")
        reg_password = st.text_input("Password", type="password")
        reg_password_repeat = st.text_input("Repeat Password", type="password")
        
        if st.button("🚀 Register Account", type="primary", width='stretch'):
            # 1. Validation Logic
            if not reg_email.endswith("@btech.au.dk"):
                st.error("Access Denied: Please use your official @btech.au.dk email.")
            elif reg_password != reg_password_repeat:
                st.error("Passwords do not match.")
            elif not (reg_username and reg_password and reg_name):
                st.error("All fields are required.")
            else:
                # 2. Check if username exists in Weaviate
                existing = user_registry.query.fetch_objects(
                    filters=Filter.by_property("username").equal(reg_username),
                    limit=1
                )
                
                if existing.objects:
                    st.error(f"Username '{reg_username}' is already taken.")
                else:
                    # 3. Hash & Insert to Cloud
                    with st.spinner("Encrypting credentials..."):
                        hashed_pw = stauth.Hasher.hash(reg_password)
                        
                        user_registry.data.insert({
                            "name": reg_name,
                            "email": reg_email,
                            "username": reg_username,
                            "password_hash": hashed_pw,
                            "role": "teacher"
                        })
                    
                    st.success(f"Successfully registered {reg_name}. You can now switch to Login.")
                    st.balloons()