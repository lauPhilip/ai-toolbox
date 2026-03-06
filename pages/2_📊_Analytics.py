import streamlit as st
import pandas as pd
import weaviate
import weaviate.classes as wvc
from weaviate.classes.init import Auth
from datetime import datetime
from wordcloud import WordCloud
from wordcloud import STOPWORDS
import matplotlib.pyplot as plt

wcd_url = st.secrets["WEAVIATE_URL"]
wcd_api_key = st.secrets["WEAVIATE_API_KEY"]

client = weaviate.connect_to_weaviate_cloud(
    cluster_url=wcd_url,
    auth_credentials=Auth.api_key(wcd_api_key),
)

st.title("📊 Course Analytics")

# Security Check: Ensure only teachers access this
if st.session_state.get("role") != "teacher":
    st.error("Access Denied.")
    st.stop()

# --- STEP 1: FETCH ONLY COURSES OWNED BY THIS TEACHER ---
memory_collection = client.collections.get("CourseBotMemory")
current_user = st.session_state.get("username")

# We query the memory to find unique course_names where administrator matches current_user
# This prevents Teacher A from seeing Teacher B's data
try:
    owned_courses_query = memory_collection.query.fetch_objects(
        filters=wvc.query.Filter.by_property("course_administrator").equal(current_user),
        return_properties=["course_name"],
        limit=1000
    )

    # Extract unique course names from the results
    teacher_courses = sorted(list(set(
        [obj.properties['course_name'] for obj in owned_courses_query.objects]
    )))

    if teacher_courses:
        selected = st.selectbox("Select one of your courses to analyze:", teacher_courses)
        
        # --- STEP 2: QUERY INTERACTION LOGS FOR THE SELECTED COURSE ---
        log_collection = client.collections.get("InteractionLogs")
        logs = log_collection.query.fetch_objects(
            filters=wvc.query.Filter.by_property("course_name").equal(selected),
            limit=100
        )

        # --- STEP 3: FORMAT & DISPLAY DATA ---
        if logs.objects:
            data = []
            for obj in logs.objects:
                raw_time = obj.properties.get('timestamp')
                
                # Robust time handling
                if isinstance(raw_time, str):
                    try:
                        formatted_time = datetime.fromisoformat(raw_time).strftime("%Y-%m-%d %H:%M")
                    except ValueError:
                        formatted_time = "Invalid Format"
                else:
                    formatted_time = "No Date Logged"

                data.append({
                    "Time": formatted_time,
                    "Student Query": obj.properties.get('user_query'),
                    "Bot Response": obj.properties.get('ai_response')
                })
            
            df = pd.DataFrame(data)

            # --- WORD CLOUD SECTION ---
            st.subheader("🔍 Common Themes")

            custom_stopwords = set(STOPWORDS).union({"please", "help", "find", "information"})
            text = " ".join(df["Student Query"].fillna("").astype(str).tolist())

            if text.strip():
                wordcloud = WordCloud(
                    stopwords=custom_stopwords,
                    width=800, 
                    height=350, 
                    background_color='white',
                    colormap='viridis'
                ).generate(text)

                # Ensure we are calling subplots from the plt (pyplot) alias
                fig, ax = plt.subplots(figsize=(10, 5)) 
                ax.imshow(wordcloud, interpolation='bilinear')
                ax.axis("off")
                
                # Use Streamlit's native plotter to render the figure
                st.pyplot(fig)
                
                # Important: Close the plot to free up memory
                plt.close(fig) 
            else:
                st.info("Not enough query data to generate a theme cloud.")

            # --- RENDER TABLE BELOW CLOUD ---
            st.subheader("📄 Interaction Logs")
            st.dataframe(
                df,
                use_container_width=True, # Recommended over width='stretch'
                hide_index=True,
                column_config={
                    "Time": st.column_config.TextColumn("Time", width="small"),
                    "Student Query": st.column_config.TextColumn(
                        "Student Query", 
                        width="medium",
                        help="The full query sent by the student"
                    ),
                    "Bot Response": st.column_config.TextColumn(
                        "Bot Response", 
                        width="large"
                    )
                }
            )
            
            # Download button at the bottom
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Logs as CSV", data=csv, file_name=f"{selected}_analytics.csv")
        else:
            st.info(f"No student interactions recorded for '{selected}' yet.")
    else:
        st.warning("No courses found under your administrator account. Have you uploaded any PDFs yet?")

except Exception as e:
    st.error(f"course-bot Database Error: {e}")