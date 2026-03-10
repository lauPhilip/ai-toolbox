import streamlit as st

# Setup the branding at the top
img1, img2 = st.columns(2)
with img1: 
    st.image("img/AU-LOGO.png", width=300)
with img2:
    st.image("img/IT-VEST-LOGO.png", width=300)
st.title("🚀 AU BTECH Course-bot Gateway")
st.markdown("##### Funded by **IT-vest - samarbejdende universiteter**")
st.divider()

st.write("Welcome to the centralized AI infrastructure for Herning. Please select your access level below:")

col1, col2 = st.columns(2)

with col1:
    with st.container(border=True):
        st.subheader("🎓 Students")
        st.write("Access Course Bots and the Prompt Library.")
        if st.button("Enter Student Portal", width='stretch', type="primary"):
            st.switch_page("student_portal.py")

with col2:
    with st.container(border=True):
        st.subheader("👨‍🏫 Staff Management")
        
        # Check if the user is ALREADY logged in
        if st.session_state.get("authentication_status"):
            st.write(f"Welcome back, **{st.session_state['name']}**. Select a tool:")
            
            # Action Cards for Staff
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("👨‍🏫 Dashboard", width='stretch'):
                    st.switch_page("pages/1_👨‍🏫_Teacher.py")
            with c2:
                if st.button("📊 Analytics", width='stretch'):
                    st.switch_page("pages/2_📊_Analytics.py")
            with c3:
                if st.button("📚 SPLibrary", width='stretch'):
                    st.switch_page("pages/3_📚_System_Prompt_Library.py")
        else:
            # Show the login button for unauthorized users
            st.write("Manage course materials and engineer prompts.")
            if st.button("Staff Login", width='stretch'):
                st.switch_page("pages/auth.py")

st.info("💡 **Tip:** If you are a student, no login is required.")