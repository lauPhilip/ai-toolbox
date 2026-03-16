import weaviate
import streamlit_authenticator as stauth
import streamlit as st

# 1. Connect to the Sensory Array
client = weaviate.connect_to_weaviate_cloud(
    cluster_url=st.secrets["WEAVIATE_URL"],
    auth_credentials=weaviate.classes.init.Auth.api_key(st.secrets["WEAVIATE_API_KEY"]),
)

try:
    user_registry = client.collections.get("UserRegistry")
    
    # 2. Fetch all users
    response = user_registry.query.fetch_objects(limit=100)
    
    st.write(f"Scanning {len(response.objects)} users for 'Salt' errors...")

    for obj in response.objects:
        u_data = obj.properties
        username = u_data["username"]
        current_hash = u_data.get("password_hash", "")

        # 3. IDENTIFY & REPAIR
        # If the hash doesn't start with $2b$ or $2a$, it's broken.
        if not str(current_hash).startswith('$2'):
            st.warning(f"Repairing signature for user: {username}")
            
            # We'll set a temporary password or you can re-hash a known one
            # For this repair, let's re-hash 'Btech2026!' as a placeholder
            new_hash = stauth.Hasher.hash("Btech2026!") 
            
            user_registry.data.update(
                uuid=obj.uuid,
                properties={
                    "password_hash": new_hash
                }
            )
            st.success(f"✅ {username} is now grounded with a valid salt.")
        else:
            st.info(f"🟢 {username} already has a valid signature.")

finally:
    client.close()