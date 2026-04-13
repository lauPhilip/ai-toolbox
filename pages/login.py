import streamlit as st
import bcrypt
import time
import weaviate.classes.query as wvc_query
from app import client # Centralized Weaviate Client

# --- 1. DOMAIN INTELLIGENCE ---
def get_role_from_email(email):
    email = email.lower()
    if "@btech.au.dk" in email:
        return "teacher"
    elif "@post.au.dk" in email or "@student.au.dk" in email:
        return "student"
    return None # Unauthorized Domain

st.title("🔐 AU Herning Gateway")
st.markdown("##### Secure access for Students and Staff.")

# Ensure the collection is accessible
user_col = client.collections.get("UserRegistry")

# --- 2. AUTH SELECTION ---
mode = st.radio("Action", ["Login", "Register"], horizontal=True, label_visibility="collapsed")

# --- LOGIN FLOW ---
if mode == "Login":
    with st.container(border=True):
        l_email = st.text_input("AU Email (@btech or @post)")
        l_pass = st.text_input("Password", type="password")
        
        if st.button("Authenticate", type="primary", use_container_width=True):
            with st.spinner("Verifying credentials..."):
                resp = user_col.query.fetch_objects(
                    filters=wvc_query.Filter.by_property("email").equal(l_email),
                    return_properties=["password_hash", "name", "role", "course_ids"],
                    limit=1
                )
                
                if resp.objects:
                    user = resp.objects[0]
                    # Verify Bcrypt Hash
                    if bcrypt.checkpw(l_pass.encode(), user.properties['password_hash'].encode()):
                        # SUCCESS: Initialize Session DNA
                        st.session_state.update({
                            "authentication_status": True,
                            "email": l_email,
                            "name": user.properties['name'],
                            "role": user.properties['role'],
                            "course_ids": user.properties.get('course_ids', "")
                        })
                        st.success(f"Access Granted. Welcome, {user.properties['name']}.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Invalid password.")
                else:
                    st.error("Account not found. Please register first.")

# --- REGISTRATION FLOW ---
else:
    with st.container(border=True):
        st.subheader("📝 New Credentials")
        r_name = st.text_input("Full Name")
        r_email = st.text_input("Official AU Email (@btech or @post)")
        r_pass = st.text_input("Create Password", type="password")
        
        if st.button("Initialize Account", use_container_width=True):
            if r_name and r_email and r_pass:
                detected_role = get_role_from_email(r_email)
                
                if not detected_role:
                    st.error("🛑 Domain Unauthorized: Only @btech.au.dk or @post.au.dk addresses allowed.")
                else:
                    # Check for duplicates in the vault
                    exists = user_col.query.fetch_objects(
                        filters=wvc_query.Filter.by_property("email").equal(r_email),
                        limit=1
                    )
                    
                    if exists.objects:
                        st.warning("Account already exists. Try logging in.")
                    else:
                        # Hash and Secure for the Registry
                        hashed = bcrypt.hashpw(r_pass.encode(), bcrypt.gensalt()).decode()
                        user_col.data.insert(properties={
                            "username": r_email,
                            "email": r_email,
                            "name": r_name,
                            "password_hash": hashed,
                            "role": detected_role,
                            "course_ids": "" # Starts empty; Teacher assigns these later
                        })
                        st.success(f"Successfully registered as **{detected_role}**!")
                        time.sleep(1)
                        st.rerun()
            else:
                st.warning("All fields required for initialization.")