import streamlit as st
import streamlit_authenticator as stauth
from weaviate.classes.query import Filter
import time
import bcrypt  # Direct engine for salt verification

# --- 1. SESSION INITIALIZATION ---
if "authenticator" not in st.session_state:
    st.error("Connection Error. Please return to the Home page.")
    st.stop()

# Accessing the Weaviate Client from session state
client = st.session_state.get("weaviate_client")
if not client:
    from app import get_weaviate_client
    client = get_weaviate_client()

user_registry = client.collections.get("UserRegistry")

# --- 2. UI HEADER ---
auth_container = st.container()

import uuid

if "auth_key" not in st.session_state:
    st.session_state["auth_key"] = str(uuid.uuid4())

with auth_container:
    st.title("👨‍🏫 Staff Access Control")
    st.divider()

    choice = st.radio("Select Action", ["Login", "Register"], horizontal=True, key=f"auth_choice_{st.session_state['auth_key']}")

    if choice == "Login":
        st.subheader("🔑 Staff Login")
        
        with st.container(border=True):
            login_user = st.text_input("Username", key="login_username_input")
            login_pass = st.text_input("Password", type="password", key="login_password_input")
            
            if st.button("Log In", type="primary", width='stretch'):
                if not login_user or not login_pass:
                    st.warning("Please enter your credentials.")
                else:
                    response = user_registry.query.fetch_objects(
                        filters=Filter.by_property("username").equal(login_user),
                        limit=1
                    )
                    
                    if response.objects:
                        user_obj = response.objects[0].properties
                        stored_hash = user_obj.get("password_hash")

                        if not stored_hash or not str(stored_hash).startswith('$'):
                            st.error(f"⚠️ Registry Error: User '{login_user}' has an unreadable signature.")
                        else:
                            try:
                                # DIRECT BCRYPT VERIFICATION (The Fix)
                                # We encode both to bytes to ensure the salt is read correctly
                                if bcrypt.checkpw(login_pass.encode('utf-8'), stored_hash.encode('utf-8')):
                                    st.session_state.update({
                                        "authentication_status": True,
                                        "username": login_user,
                                        "email": user_obj["email"],
                                        "name": user_obj["name"],
                                        "role": user_obj["role"]
                                    })
                                    st.success(f"Welcome back, {user_obj['name']}!")
                                    time.sleep(1)
                                    st.switch_page("landing.py")
                                else:
                                    st.error("Incorrect password.")
                            except Exception as e:
                                st.error(f"🔒 Encryption Error: {e}")
                                st.info("This usually occurs if the stored hash is malformed. Try re-registering the user.")
                    else:
                        st.error("User not found.")

    else:
        st.subheader("📝 Create Staff Account")
        with st.container(border=True):
            reg_name = st.text_input("Full Name", key="reg_name")
            reg_email = st.text_input("Email (@btech.au.dk)", key="reg_email")
            reg_username = st.text_input("Username", key="reg_user")
            reg_password = st.text_input("Password", type="password", key="reg_pass")
            reg_password_repeat = st.text_input("Repeat Password", type="password", key="reg_pass_rep")
            
            if st.button("🚀 Register Account", type="primary", width='stretch'):
                if not reg_email.endswith("@btech.au.dk"):
                    st.error("Access Denied: Use an official @btech.au.dk email.")
                elif reg_password != reg_password_repeat:
                    st.error("Passwords do not match.")
                elif not (reg_username and reg_password and reg_name):
                    st.error("All fields are required.")
                else:
                    existing = user_registry.query.fetch_objects(
                        filters=Filter.by_property("username").equal(reg_username),
                        limit=1
                    )
                    
                    if existing.objects:
                        st.error(f"Username '{reg_username}' is already taken.")
                    else:
                        with st.spinner("Securing Signature..."):
                            # Fix: stauth.Hasher.hash returns a LIST. We take the first element [0].
                            final_hash = stauth.Hasher.hash(reg_password)
    
                            user_registry.data.insert({
                                "username": reg_username,
                                "password_hash": final_hash,
                                "name": reg_name,
                                "email": reg_email,
                                "role": "teacher"
                            })
                        
                        st.success(f"Registered {reg_name}. You can now log in.")
                        st.balloons()