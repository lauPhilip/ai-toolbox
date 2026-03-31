import streamlit as st
import pandas as pd
import weaviate
import weaviate.classes.query as wvc_query
from weaviate.classes.init import Auth
from datetime import datetime
from wordcloud import WordCloud, STOPWORDS
import matplotlib.pyplot as plt
from collections import Counter
import re

# --- 1. WEAVIATE CONNECTION ---
@st.cache_resource
def get_weaviate_client():
    return weaviate.connect_to_weaviate_cloud(
        cluster_url=st.secrets["WEAVIATE_URL"],
        auth_credentials=Auth.api_key(st.secrets["WEAVIATE_API_KEY"]),
    )

client = get_weaviate_client()

st.title("📊 Analytics")

# --- SECURITY CHECK ---
user_email = st.session_state.get("email")
if st.session_state.get("role") != "teacher" or not user_email:
    st.error("Access Denied: teachers only.")
    st.stop()

# --- STEP 1: IDENTIFY ACCESSIBLE COURSES ---
# We look into the Registry to see which courses this user is linked to
registry = client.collections.get("CourseRegistry")

try:
    # Filter: I am Responsible OR I am an Associated Teacher
    my_courses_query = registry.query.fetch_objects(
        filters=wvc_query.Filter.by_property("responsible_email").equal(user_email) | 
                wvc_query.Filter.by_property("teacher_emails").contains_any([user_email]),
        return_properties=["course_name", "course_id"],
        limit=100
    )

    my_course_names = sorted(list(set([obj.properties['course_name'] for obj in my_courses_query.objects])))

    if not my_course_names:
        st.warning("No registered courses found linked to your email.")
        st.stop()

    # --- STEP 2: DUAL-TIER SELECTION ---
    c_col, b_col = st.columns(2)
    with c_col:
        selected_course = st.selectbox("🎯 Select Course:", my_course_names)

    # Fetch unique bots that have interactions logged for this course
    log_collection = client.collections.get("InteractionLogs")
    bot_list_query = log_collection.query.fetch_objects(
        filters=wvc_query.Filter.by_property("course_name").equal(selected_course),
        return_properties=["bot_name"],
        limit=500
    )
    available_bots = sorted(list(set([obj.properties.get('bot_name', 'General Bot') for obj in bot_list_query.objects])))

    with b_col:
        selected_bot = st.selectbox("🤖 Select CourseBot:", ["All Bots"] + available_bots)

    # --- STEP 3: FETCH & PARSE LOG DATA ---
    # Define Filter: Always filter by Course, optionally by Bot
    final_filter = wvc_query.Filter.by_property("course_name").equal(selected_course)
    if selected_bot != "All Bots":
        final_filter = final_filter & wvc_query.Filter.by_property("bot_name").equal(selected_bot)

    logs = log_collection.query.fetch_objects(
        filters=final_filter,
        limit=500,
        sort=wvc_query.Sort.by_property("timestamp", ascending=False)
    )

    if logs.objects:
        data = []
        for obj in logs.objects:
            # FIXED: Robust Timestamp Parsing
            ts_raw = obj.properties.get('timestamp')
            formatted_time = "Unknown"
            
            if ts_raw:
                try:
                    # ISO format handling (handles 2026-03-05T15:21:55Z)
                    dt_obj = datetime.fromisoformat(str(ts_raw).replace('Z', '+00:00'))
                    formatted_time = dt_obj.strftime("%d %b, %H:%M")
                except:
                    formatted_time = "Format Error"

            data.append({
                "Time": formatted_time,
                "Bot": obj.properties.get('bot_name', 'N/A'),
                "Query": obj.properties.get('user_query'),
                "Response": obj.properties.get('ai_response'),
                "RawTime": ts_raw # Used for sorting if needed
            })
        
        df = pd.DataFrame(data)

        # --- VISUALIZATION: WORD CLOUD ---
        st.subheader(f"🔍 Theme Cloud: {selected_bot}")
        
        text = " ".join(df["Query"].fillna("").astype(str).tolist())
        if len(text.strip()) > 10:
            custom_stopwords = set(STOPWORDS).union({"please", "help", "find", "how", "what", "is"})
            wordcloud = WordCloud(
                stopwords=custom_stopwords,
                width=1000, height=400,
                background_color='white',
                colormap='plasma'
            ).generate(text)

            fig, ax = plt.subplots(figsize=(10, 4))
            ax.imshow(wordcloud, interpolation='bilinear')
            ax.axis("off")
            st.pyplot(fig)
            plt.close(fig)
        else:
            st.info("Insufficient query volume for a theme cloud.")

        # --- VISUALIZATION: TOP TERMS ---
        st.subheader("📊 Top Trending Concepts")
        words = re.findall(r'\w+', text.lower())
        stop_list = {'the', 'and', 'for', 'this', 'that', 'with', 'from', 'are', 'was'}
        filtered = [w for w in words if w not in stop_list and len(w) > 3]
        
        if filtered:
            counts = Counter(filtered).most_common(12)
            chart_df = pd.DataFrame(counts, columns=['Term', 'Count']).set_index('Term')
            st.bar_chart(chart_df)

        # --- INTERACTION TABLE ---
        st.subheader("📑 Interaction History")
        st.dataframe(
            df[["Time", "Bot", "Query", "Response"]],
            hide_index=True,
            use_container_width=True,
            column_config={
                "Time": st.column_config.TextColumn("Timestamp", width="small"),
                "Query": st.column_config.TextColumn("Student input", width="medium"),
                "Response": st.column_config.TextColumn("course-bot response", width="large")
            }
        )

        # --- DOWNLOAD ---
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(f"📥 Export {selected_course} Logs", data=csv, file_name=f"analytics_{selected_course}.csv")

    else:
        st.info(f"No recorded intelligence for '{selected_course}' yet.")

except Exception as e:
    st.error(f"Analytics Engine Stalled: {e}")