import streamlit as st
import streamlit_authenticator as stauth
from weaviate.classes.query import Filter
import time
import bcrypt # Add this at the top of your file

# --- 1. SESSION INITIALIZATION ---
# Check if the authenticator exists to prevent double-rendering or crashes
if "authenticator" not in st.session_state:
    st.error("L.U.M.A. Connection Error. Please return to the Home page.")
    st.stop()

# Using the cached client established in app.py
client = st.session_state.get("weaviate_client")
if not client:
    from app import get_weaviate_client
    client = get_weaviate_client()

authenticator = st.session_state["authenticator"]
user_registry = client.collections.get("UserRegistry")

# --- 2. UI HEADER ---
# We use a container to keep everything grouped and prevent duplication
auth_container = st.container()

with auth_container:
    st.title("👨‍🏫 Staff Access Control")
    st.divider()

    # The Radio button is the primary toggle
    choice = st.radio("Select Action", ["Login", "Register"], horizontal=True, key="auth_choice")

    if choice == "Login":
        st.subheader("🔑 Staff Login")
        
        with st.container(border=True):
            # Unique keys prevent Streamlit from confusing these with other inputs
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
                        # 1. Force the hash to be a clean, leading-space-free string
                        raw_hash = user_obj.get("password_hash")
                        stored_hash = str(raw_hash).strip() if raw_hash else None

                        if not stored_hash or not stored_hash.startswith('$'):
                            st.error(f"⚠️ Registry Error: User '{login_user}' has an incomplete signature.")
                        else:
                            try:
                                # 2. THE SECRET SAUCE:
                                # Some versions of bcrypt/stauth require the hash to be exactly as stored
                                # We pass the clean string directly.
                                if stauth.Hasher.check_pw(stored_hash, login_pass):
                                    st.session_state.update({
                                        "authentication_status": True,
                                        "username": login_user,
                                        "name": user_obj["name"],
                                        "role": user_obj["role"]
                                    })
                                    st.success(f"Welcome back, {user_obj['name']}!")
                                    time.sleep(1)
                                    st.switch_page("landing.py")
                                else:
                                    st.error("Incorrect password.")
                            except ValueError as e:
                                # This is where the 'Invalid Salt' lives
                                st.error(f"🔒 Encryption Error: {e}")
                                st.info("Technical Note: This usually means the hash format is correct but the library version has a conflict.")
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
                        with st.spinner("Encrypting..."):
                            # Generate the hash object
                            hashed_pw = stauth.Hasher.hash(reg_password)
                            
                            # Ensure it's a clean string, not a byte object or a wrapped string
                            final_hash = str(hashed_pw).strip()
                            
                            user_registry.data.insert({
                                "username": reg_username,
                                "password_hash": final_hash, # Save the clean string
                                "name": reg_name,
                                "email": reg_email,
                                "role": "teacher"
                            })
                        st.success(f"Registered {reg_name}. You can now log in.")
                        st.balloons()