import weaviate.classes.query as wvc_query
from app import client # Assuming your client is initialized here
import streamlit as st
import streamlit as st
import streamlit_authenticator as stauth
import weaviate
from weaviate.classes.init import Auth
import weaviate.classes.config as wvc
from weaviate.classes.query import Filter
import os

def get_weaviate_client():
    return weaviate.connect_to_weaviate_cloud(
        cluster_url=st.secrets["WEAVIATE_URL"],
        auth_credentials=Auth.api_key(st.secrets["WEAVIATE_API_KEY"])
    )

client = get_weaviate_client()

# --- TARGETS TO PURGE ---
ghost_bots = [
    "Web Technologies"
]

st.info("🧹 Initiating deep vault cleanup...")

# collections to scrub
target_collections = ["InteractionLogs"]

for coll_name in target_collections:
    try:
        coll = client.collections.get(coll_name)
        for bot in ghost_bots:
            result = coll.data.delete_many(
                where=wvc_query.Filter.by_property("course_name").equal(bot)
            )
            if result.successful > 0:
                st.success(f"Purged {result.successful} records of '{bot}' from {coll_name}.")
    except Exception as e:
        st.error(f"Error scrubbing {coll_name}: {e}")

st.write("✨ Slate is clean. Only new, properly anchored courses will appear now.")

client.close()