import streamlit as st
import ollama
import chromadb

# --- SECURITY DEADBOLT ---
if not st.session_state.get("authentication_status"):
    st.error("🔒 Please log in on the Home page to access course materials.")
    st.stop()

client = chromadb.PersistentClient(path="./chroma_db")
st.title("🎓 Student Portal")

existing_bots = [c.name for c in client.list_collections()]
selected_bot = st.selectbox("Choose your Course", ["Select..."] + existing_bots)

if selected_bot != "Select...":
    collection = client.get_collection(name=selected_bot)
    
    # --- CHAT LOGIC ---
    if "messages" not in st.session_state or st.session_state.get("last_bot") != selected_bot:
        st.session_state.messages = []
        st.session_state.last_bot = selected_bot

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask about the course..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.spinner("Searching course materials..."):
            results = collection.query(query_texts=[prompt], n_results=5)
            
            # --- FIX: STABLE SOURCE MAPPING ---
            # Map unique filenames to a stable [n] index
            unique_sources = sorted(list(set([m.get("source", "Unknown") for m in results['metadatas'][0]])))
            source_map = {name: i + 1 for i, name in enumerate(unique_sources)}
            
            # Build context labeled with the stable number
            context_with_ids = []
            for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
                src_num = source_map.get(meta.get("source", "Unknown"), 0)
                context_with_ids.append(f"SOURCE [{src_num}]: {doc}")
            
            context = "\n\n".join(context_with_ids)
            source_footer_list = [f"[{num}] {name}" for name, num in source_map.items()]
            
            base_prompt = collection.metadata.get("prompt", "Factual academic assistant.")
            full_sys_prompt = f"""
            {base_prompt}
            STRICT RULES:
            1. ONLY answer using the provided context. 
            2. If information is missing, say: "I'm sorry, I don't have enough information in the materials to answer that."
            3. Every sentence using info from the context MUST end with the source number in brackets, e.g., [1].
            4. If a sentence uses info from multiple sources, use [1, 2].
            5. Do NOT use labels like 'Statement'. Just append the number in brackets.
            6. Ignore all professor names or university administrative details.
            """

        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            full_response = ""
            
            for chunk in ollama.chat(
                model='phi3', 
                messages=[{'role': 'system', 'content': full_sys_prompt},
                          {'role': 'user', 'content': f"CONTEXT:\n{context}\n\nQUESTION: {prompt}"}], 
                stream=True
            ):
                full_response += chunk['message']['content']
                response_placeholder.markdown(full_response + "▌")
            
            if "I'm sorry" not in full_response:
                final_content = full_response + "\n\n---\n**Sources used in this answer:**\n" + "\n".join(source_footer_list)
            else:
                final_content = full_response
                
            response_placeholder.markdown(final_content)
            st.session_state.messages.append({"role": "assistant", "content": final_content})