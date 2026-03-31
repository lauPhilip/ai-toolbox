import streamlit as st
import weaviate.classes.config as wvc
from mistralai.client import Mistral
import weaviate.classes.query as wvc_query
import json
import re

# --- 2. INITIALIZATION & STATE MANAGEMENT ---
if "form_id" not in st.session_state:
    st.session_state["form_id"] = 0
if "scraped_data" not in st.session_state:
    st.session_state["scraped_data"] = None

def reset_registry_form():
    """Clears the input field and resets the AI cache."""
    st.session_state["form_id"] += 1
    st.session_state["scraped_data"] = None
    st.rerun()

# --- 3. AI EXTRACTION ENGINE (Mistral-Medium) ---
def parse_with_ai(raw_text):
    """Passes raw text to Mistral to extract a structured Course JSON."""
    mistral_client = Mistral(api_key=st.secrets["MISTRAL_KEY"])
    
    system_prompt = """
    You are course-bot. Extract AU course data into JSON.
    Fields: course_id, course_name, ects (int), course_responsible, responsible_email, 
    associated_teachers (list of names), teacher_emails (list of emails), learning_outcomes.
    Return ONLY valid JSON. Use "Not Found" for missing strings. Ensure ECTS is a number.
    """
    try:
        response = mistral_client.chat.complete(
            model="mistral-medium-latest",
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user", "content": raw_text[:15000]}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"L.U.M.A. AI Analysis Failed: {e}")
        return None

# --- UI LAYER ---
st.title("🏫 Course Management")
st.markdown("##### Synchronize AU Kursuskatalog DNA with the Registry.")

tab1, tab2 = st.tabs(["🆕 Register New Course", "🛠️ Edit/Delete Registry"])

# --- TAB 1: REGISTRATION ---
with tab1:
    with st.container(border=True):
        st.subheader("📡 Intelligence Intake")
        st.info("💡 **Tip:** Since the AU Catalog has high security, Copy (Ctrl+A) and Paste (Ctrl+V) the course page text below.")
        
        # Dynamic key based on form_id ensures the field clears on reset
        manual_text = st.text_area("Paste Raw Course Content", height=200, 
                                   key=f"input_{st.session_state['form_id']}",
                                   placeholder="Paste the course catalog content here...")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🤖 Analyze with Mistral", type="primary", use_container_width=True):
                if manual_text:
                    with st.spinner("Mistral-Medium is parsing the DNA..."):
                        st.session_state["scraped_data"] = parse_with_ai(manual_text)
                        st.rerun()
                else:
                    st.warning("Please paste some content first, Master Lau.")
        with col2:
            if st.button("🗑️ Reset Form", use_container_width=True):
                reset_registry_form()

    # The Verification Form (Appears only after AI analysis)
    if st.session_state["scraped_data"]:
        st.divider()
        data = st.session_state["scraped_data"]
        
        with st.form("verify_course_form"):
            st.subheader("🛠️ Verify & Save Course")
            c_left, c_right = st.columns(2)
            
            with c_left:
                name = st.text_input("Course Name", value=data.get("course_name"))
                cid = st.text_input("Course ID", value=data.get("course_id"))
                # Defaulting to 0 if ECTS is not a number
                ects_val = data.get("ects", 0)
                ects = st.number_input("ECTS", value=int(ects_val) if str(ects_val).isdigit() else 0)
            
            with c_right:
                resp = st.text_input("Responsible Name", value=data.get("course_responsible"))
                rem = st.text_input("Responsible Email", value=data.get("responsible_email"))
                
                t_list = data.get("associated_teachers", [])
                e_list = data.get("teacher_emails", [])
                teachers = st.text_area("Teachers (comma separated)", value=", ".join(t_list) if isinstance(t_list, list) else str(t_list))
                emails = st.text_area("Teacher Emails (comma separated)", value=", ".join(e_list) if isinstance(e_list, list) else str(e_list))
            
            outcomes = st.text_area("Learning Outcomes", value=data.get("learning_outcomes"), height=200)
            
            if st.form_submit_button("✅ Secure in Registry", type="primary", use_container_width=True):
                from app import client # Using your cached client from app.py
                
                # Ensure the collection exists
                if not client.collections.exists("CourseRegistry"):
                     client.collections.create(
                        name="CourseRegistry",
                        properties=[
                            wvc.Property(name="course_id", data_type=wvc.DataType.TEXT),
                            wvc.Property(name="course_name", data_type=wvc.DataType.TEXT),
                            wvc.Property(name="ects", data_type=wvc.DataType.INT),
                            wvc.Property(name="course_responsible", data_type=wvc.DataType.TEXT),
                            wvc.Property(name="responsible_email", data_type=wvc.DataType.TEXT),
                            wvc.Property(name="associated_teachers", data_type=wvc.DataType.TEXT_ARRAY),
                            wvc.Property(name="teacher_emails", data_type=wvc.DataType.TEXT_ARRAY),
                            wvc.Property(name="learning_outcomes", data_type=wvc.DataType.TEXT),
                        ]
                    )
                
                # Insert the Course DNA
                registry = client.collections.get("CourseRegistry")
                registry.data.insert(properties={
                    "course_id": cid, "course_name": name, "ects": ects,
                    "course_responsible": resp, "responsible_email": rem,
                    "associated_teachers": [t.strip() for t in teachers.split(",") if t.strip()],
                    "teacher_emails": [e.strip() for e in emails.split(",") if e.strip()],
                    "learning_outcomes": outcomes
                })
                st.success(f"Intelligence Secured: {name} is now official.")
                st.balloons()
                reset_registry_form()

# --- TAB 2: EDIT / DELETE REGISTRY ---
with tab2:
    st.subheader("📋 Active Course Registry")
    from app import client
    
    # Identity Anchor
    user_email = st.session_state.get("email")
    
    if not user_email:
        st.warning("📡 Identity Signal Lost. Please log in again to manage courses.")
    else:
        registry = client.collections.get("CourseRegistry")
        
        try:
            # Multi-Role Query: Show if I am responsible OR associated
            response = registry.query.fetch_objects(
                filters=wvc_query.Filter.by_property("responsible_email").equal(user_email) | 
                        wvc_query.Filter.by_property("teacher_emails").contains_any([user_email]),
                limit=100
            )
            
            if not response.objects:
                st.info("No courses currently assigned to your command.")
            else:
                for obj in response.objects:
                    p = obj.properties
                    is_resp = p.get('responsible_email') == user_email
                    role_tag = "⭐ Responsible" if is_resp else "👤 Teacher"
                    
                    with st.expander(f"{role_tag} | {p['course_name']} ({p['course_id']})"):
                        with st.form(key=f"edit_{obj.uuid}"):
                            col_a, col_b = st.columns(2)
                            with col_a:
                                e_name = st.text_input("Course Name", value=p.get('course_name'))
                                e_cid = st.text_input("Course ID", value=p.get('course_id'))
                                e_ects = st.number_input("ECTS", value=int(p.get('ects', 0)))
                            with col_b:
                                e_resp = st.text_input("Responsible", value=p.get('course_responsible'))
                                e_rem = st.text_input("Email", value=p.get('responsible_email'))
                                
                                # List conversion for editing
                                t_str = ", ".join(p.get('associated_teachers', []))
                                m_str = ", ".join(p.get('teacher_emails', []))
                                e_teachers = st.text_area("Teachers", value=t_str)
                                e_emails = st.text_area("Teacher Emails", value=m_str)

                            e_outcomes = st.text_area("Learning Outcomes", value=p.get('learning_outcomes'), height=150)

                            if st.form_submit_button("💾 Save All Changes", type="primary", use_container_width=True):
                                registry.data.update(
                                    uuid=obj.uuid,
                                    properties={
                                        "course_name": e_name, "course_id": e_cid, "ects": e_ects,
                                        "course_responsible": e_resp, "responsible_email": e_rem,
                                        "associated_teachers": [x.strip() for x in e_teachers.split(",") if x.strip()],
                                        "teacher_emails": [y.strip() for y in e_emails.split(",") if y.strip()],
                                        "learning_outcomes": e_outcomes
                                    }
                                )
                                st.success("Registry Updated.")
                                st.rerun()

                        # DELETE GATEKEEPER
                        if is_resp:
                            if st.button("🗑️ Delete Course", key=f"del_{obj.uuid}", type="secondary", use_container_width=True):
                                registry.data.delete_by_id(obj.uuid)
                                st.warning("Course purged from registry.")
                                st.rerun()
                        else:
                            st.caption("ℹ️ Only the Course Responsible can delete this registry.")

        except Exception as e:
            st.error(f"Vault Communication Failure: {e}")