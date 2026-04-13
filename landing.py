import streamlit as st

st.title("🚀 AU BTECH Course-bot Gateway")
st.markdown("##### Funded by **IT-vest - samarbejdende universiteter**")
st.divider()

# Identity Check
is_logged_in = st.session_state.get("authentication_status")
role_raw = st.session_state.get("role")
user_role = str(role_raw).lower() if role_raw else ""

# Layout Grid
col1, col2 = st.columns(2)

# --- COLUMN 1: STUDENT HUB ---
with col1:
    with st.container(border=True):
        st.subheader("🎓 Student Hub")
        if is_logged_in:
            # Both Students and Teachers can enter the portal, but we hide the login/demo
            st.write(f"Access the course bots as **{user_role.capitalize()}**.")
            if st.button("🚀 Enter Student Portal (Chat)", use_container_width=True, type="primary"):
                st.switch_page("chat.py")
        else:
            # Only Guests see these
            st.write("Access AI Course Bots and Assignment Briefings.")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🕵️ Guest Demo", use_container_width=True):
                    st.switch_page("chat.py")
            with c2:
                if st.button("🔐 Login", use_container_width=True, type="primary"):
                    st.switch_page("pages/login.py")

# --- COLUMN 2: STAFF MANAGEMENT ---
# We hide this column entirely if a Student is logged in
if user_role != "student":
    with col2:
        with st.container(border=True):
            st.subheader("👨‍🏫 Staff Management")
            if is_logged_in and user_role == "teacher":
                st.write(f"Logged in as Staff: **{st.session_state['name']}**")
                if st.button("👨‍🏫 Teacher Dashboard", use_container_width=True, type="primary"):
                    st.switch_page("pages/1_👨‍🏫_Teacher.py")
            else:
                # This only shows for Guests
                st.write("Engineer course materials and evaluate analytics.")
                if st.button("Staff Login", use_container_width=True):
                    st.switch_page("pages/login.py")

# Clean Status Bar
if is_logged_in:
    st.success(f"✔️ Currently authenticated as **{st.session_state['name']}** ({user_role.capitalize()})")
else:
    st.info("💡 **Tip:** Login with your AU account to unlock assigned course materials.")