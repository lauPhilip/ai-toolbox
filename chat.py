import streamlit as st
import weaviate
from weaviate.classes.init import Auth, AdditionalConfig, Timeout
from weaviate.classes.query import Filter
from mistralai.client import Mistral
import time

# --- 1. THE ULTIMATE CLOUD BRIDGE ---
@st.cache_resource 
def get_weaviate_client():
    return weaviate.connect_to_weaviate_cloud(
        cluster_url=st.secrets["WEAVIATE_URL"],
        auth_credentials=Auth.api_key(st.secrets["WEAVIATE_API_KEY"]),
        headers={"X-Mistral-Api-Key": st.secrets["MISTRAL_KEY"]},
        additional_config=AdditionalConfig(
            # Extreme patience for Cloud-to-Cloud communication
            timeout=Timeout(query=300, connect=60, init=300) 
        )
    )

client = get_weaviate_client()
mistral_client = Mistral(api_key=st.secrets["MISTRAL_KEY"])

# --- 2. THE CHAT INTERFACE ---
st.title("🎓 BMI Course Bot")
TARGET_COURSE = "Technological Business Model Innovation (480142U066)"

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- 3. THE RESILIENT RETRIEVAL ---
user_query = st.chat_input("Enter your BMI case study details...")

if user_query:
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        with st.spinner("Accessing the AU Vault..."):
            try:
                collection = client.collections.get("CourseBotMemory")
                
                # We use a very high-speed search first
                results = collection.query.hybrid(
                    query=user_query,
                    filters=Filter.by_property("course_name").equal(TARGET_COURSE),
                    limit=3,
                    alpha=0.5 # Balanced for cloud stability
                )
                
                if results.objects:
                    context = "\n".join([o.properties['chunk'] for o in results.objects])
                    
                    # Call Mistral
                    response = mistral_client.chat.complete(
                        model="mistral-medium-latest",
                        messages=[
                            {"role": "system", "content": "You are a Business Model expert. Use ONLY the provided context."},
                            {"role": "user", "content": f"CONTEXT:\n{context}\n\nQUERY: {user_query}"}
                        ]
                    )
                    
                    answer = response.choices[0].message.content
                    placeholder.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                else:
                    st.warning("No context found for this query.")
                    
            except Exception as e:
                # If the cloud still fails, we provide a manual retry button
                st.error(f"Cloud Latency Detected. [Technical: {e}]")
                if st.button("🔄 Force Reconnect & Retry"):
                    st.rerun()