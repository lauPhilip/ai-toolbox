import streamlit as st
import weaviate.classes.query as wvc_query
from app import client # Centralized Client

# --- 1. IDENTITY & MULTI-ROLE CLEARANCE ---
auth_status = st.session_state.get("authentication_status")
user_role = str(st.session_state.get("role")).lower()
user_email = st.session_state.get("email")

if not auth_status:
    st.error("Authentication required. Please login to access course hubs.")
    st.stop()

st.title("📂 Course Hub")

# Logic to determine which courses this user can see
registry = client.collections.get("CourseRegistry")

if user_role == "teacher":
    st.info("👨‍🏫 **Staff Preview Mode**: Viewing hubs where you are listed as Responsible or Associated Teacher.")
    # Fetch courses where this teacher is involved
    course_resp = registry.query.fetch_objects(
        filters=wvc_query.Filter.by_property("responsible_email").equal(user_email) | 
                wvc_query.Filter.by_property("teacher_emails").contains_any([user_email]),
        limit=100
    )
else:
    # Student Logic: Fetch assigned course IDs from session
    raw_courses = st.session_state.get("course_ids", "")
    my_course_ids = [c.strip() for c in raw_courses.split(",") if c.strip()]
    
    if not my_course_ids:
        st.info("👋 Your account is active, but you haven't been enrolled in any courses yet.")
        st.stop()
        
    course_resp = registry.query.fetch_objects(
        filters=wvc_query.Filter.by_property("course_id").contains_any(my_course_ids),
        limit=100
    )

# --- 2. COURSE SELECTION ---
course_options = {f"{o.properties['course_name']} ({o.properties['course_id']})": o.properties['course_id'] 
                  for o in course_resp.objects}

if not course_options:
    st.warning("No active tracks found for your profile.")
    st.stop()

selected_label = st.selectbox("🎯 Select Track to View:", options=list(course_options.keys()))
active_course_id = course_options[selected_label]
active_course_name = selected_label.split(" (")[0]

st.divider()

# --- 3. THE HUB RESOURCES ---
tab_bots, tab_assign, tab_prompts = st.tabs(["🤖 Course Bots", "📝 Assignments", "📋 Prompt Library"])

# --- TAB: COURSE BOTS ---
with tab_bots:
    st.subheader("Intelligence Arrays")
    bot_memory = client.collections.get("CourseBotMemory")
    bots_resp = bot_memory.query.fetch_objects(
        filters=wvc_query.Filter.by_property("course_id").equal(active_course_id),
        return_properties=["bot_name"],
        limit=100
    )
    
    unique_bots = sorted(list(set([b.properties.get("bot_name") for b in bots_resp.objects])))
    
    if not unique_bots:
        st.info("No bots have been deployed for this track yet.")
    else:
        for bot in unique_bots:
            with st.container(border=True):
                c1, c2 = st.columns([0.8, 0.2])
                c1.write(f"**{bot}**")
                if c2.button("🚀 Launch", key=f"launch_{bot}"):
                    st.session_state["preselected_course"] = active_course_name
                    st.session_state["preselected_bot"] = bot
                    st.switch_page("chat.py")

# --- TAB: ASSIGNMENTS ---
with tab_assign:
    st.subheader("Active Missions")
    assign_col = client.collections.get("AssignmentRegistry")
    assign_resp = assign_col.query.fetch_objects(
        filters=wvc_query.Filter.by_property("course_id").equal(active_course_id),
        limit=50
    )
    
    if not assign_resp.objects:
        st.info("No active assignments found.")
    else:
        for a in assign_resp.objects:
            with st.expander(f"📝 {a.properties['title']}"):
                st.write("**Objective:**")
                st.write(a.properties['description'])
                st.write("**Learning Outcomes:**")
                st.write(a.properties['learning_outcomes'])
                # Teachers can see that the submit button exists, but it's disabled for preview
                st.button("📤 Submit Work (Student Only)", key=f"sub_{a.uuid}", disabled=True, use_container_width=True)

# --- TAB: PROMPT LIBRARY ---
with tab_prompts:
    st.subheader("Tactical Templates")
    # Using your existing student prompt library collection
    if client.collections.exists("StudentPromptLibrary"):
        prompt_col = client.collections.get("StudentPromptLibrary")
        p_resp = prompt_col.query.fetch_objects(
            filters=wvc_query.Filter.by_property("course_id").equal(active_course_id),
            limit=50
        )
        if not p_resp.objects:
            st.info("No templates found for this track.")
        else:
            for p in p_resp.objects:
                with st.container(border=True):
                    st.write(f"**{p.properties['title']}**")
                    st.caption(p.properties['description'])
                    st.code(p.properties['prompt_text'], language="text")
    else:
        st.info("Prompt Library is currently offline.")