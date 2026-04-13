import streamlit as st
import json
import time
import requests
from datetime import datetime
from mistralai.client import Mistral

# --- 1. RESEARCH LEDGER PROTOCOL ---
def log_to_ledger(ledger, agent_name, step, decision, evidence, prompts=None):
    entry = {
        "agent": agent_name,
        "step": step,
        "decision": decision,
        "evidence_grounding": evidence,
        "prompt_history": prompts,
        "timestamp": datetime.now().isoformat()
    }
    ledger["decisions"].append(entry)
    return ledger

# --- 2. MULTI-SOURCE RETRIEVAL TOOLS ---
def search_semantic_scholar(query, limit=10):
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={query}&limit={limit}&fields=title,abstract,url,year,authors"
    try:
        response = requests.get(url, timeout=15)
        return response.json().get("data", []) if response.status_code == 200 else []
    except:
        return []

def search_google_scholar(query, limit=10):
    """Retrieves papers via SerpApi (Google Scholar). Requires SERP_API_KEY in secrets."""
    if "SERP_API_KEY" not in st.secrets:
        st.error("Missing SERP_API_KEY in secrets. Skipping Google Scholar.")
        return []
    
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_scholar",
        "q": query,
        "api_key": st.secrets["SERP_API_KEY"],
        "num": limit
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        results = response.json().get("organic_results", [])
        # Format SerpApi output to match our internal paper schema
        formatted = [{"title": r.get("title"), "abstract": r.get("snippet"), "url": r.get("link"), "year": None} for r in results]
        return formatted
    except:
        return []

# --- 3. THE COMPLETE PRISMA PIPELINE ---
def run_prisma_review(mistral_client, user_query, criteria, limit, ledger):
    # --- PHASE 1: DUAL-RETRIEVAL ---
    candidates = []
    with st.status("📡 Phase 1: Retrieval Agent (Dual-Source identification)", expanded=True):
        st.write("Optimizing Academic Boolean Syntax...")
        
        # Librarian Translation
        translation_prompt = f"Convert to a simple academic search string (no nested parens). Intent: {user_query}"
        opt_resp = mistral_client.chat.complete(
            model="mistral-large-latest",
            messages=[{"role": "system", "content": "You are an Academic Search Optimizer."},
                      {"role": "user", "content": translation_prompt}]
        )
        optimized_query = opt_resp.choices[0].message.content.strip().replace('"', '')
        
        st.write(f"Searching Semantic Scholar & Google Scholar for: `{optimized_query}`")
        
        # Execute Dual Search
        s2_results = search_semantic_scholar(optimized_query, limit=limit)
        gs_results = search_google_scholar(optimized_query, limit=limit)
        
        # Merge and De-duplicate by title
        seen_titles = set()
        for p in (s2_results + gs_results):
            title_clean = p['title'].lower().strip()
            if title_clean not in seen_titles:
                candidates.append(p)
                seen_titles.add(title_clean)
            
        log_to_ledger(ledger, "Retrieval Agent", "Identification", 
                      f"Found {len(candidates)} unique papers across 2 sources", optimized_query)

    if not candidates:
        st.error("❌ No papers found. Mission Aborted.")
        return None, []
    
    st.info(f"✅ **Identification Complete**: {len(candidates)} unique candidate papers identified.")
    with st.expander("View Candidate List"):
        for p in candidates:
            st.write(f"- {p['title']}")

    # --- PHASE 2: SCREENING ---
    included_papers = []
    with st.status("🛡️ Phase 2: Screening Agent (Eligibility)", expanded=True):
        for paper in candidates:
            screening_prompt = f"CRITERIA: {criteria}\nTITLE: {paper['title']}\nABSTRACT: {paper.get('abstract')}\nDecision (JSON: {{'decision': 'Include/Exclude', 'reasoning': '...'}})"
            
            resp = mistral_client.chat.complete(
                model="mistral-large-latest",
                messages=[{"role": "system", "content": "You are a PRISMA Screening Agent."},
                          {"role": "user", "content": screening_prompt}],
                response_format={"type": "json_object"}
            )
            res = json.loads(resp.choices[0].message.content)
            
            if res['decision'] == "Include":
                included_papers.append(paper)
                st.success(f"**Accepted**: {paper['title']}")
            else:
                st.error(f"**Excluded**: {paper['title']}")
            
            log_to_ledger(ledger, "Screening Agent", "Screening", res['decision'], res['reasoning'])

    # --- PHASE 3: SYNTHESIS ---
    if included_papers:
        with st.status("✍️ Phase 3: Synthesis Agent (Writing-As-Reasoning)", expanded=True):
            context = "\n\n".join([f"Title: {p['title']}\nAbstract: {p.get('abstract')}" for p in included_papers])
            final_resp = mistral_client.chat.complete(
                model="mistral-large-latest",
                messages=[{"role": "system", "content": "Senior Academic Synthesis Agent."},
                          {"role": "user", "content": f"CONTEXT:\n{context}\n\nSynthesize PRISMA review for: {user_query}"}]
            )
            report = final_resp.choices[0].message.content
            log_to_ledger(ledger, "Synthesis Agent", "Final Review", "Synthesis Generated", report)
            return report, included_papers
    
    return None, []

# --- 4. COMMAND CENTER ---
st.title("🔬 Literature Review Agent (TraceableAI)")

with st.container(border=True):
    st.subheader("⚙️ Mission Parameters")
    review_query = st.text_input("Research Query", value="AI forecasting in Supply Chain")
    review_scope = st.text_area("Inclusion Criteria", value="Peer-reviewed, post-2020. Focus on deep learning.")
    search_limit = st.slider("Papers per source", 5, 20, 10)

    if st.button("🚀 Execute Dual-Source PRISMA Review", type="primary", use_container_width=True):
        ledger = {"metadata": {"query": review_query, "timestamp": datetime.now().isoformat()}, "decisions": []}
        mistral_client = Mistral(api_key=st.secrets["MISTRAL_KEY"])

        report, papers = run_prisma_review(mistral_client, review_query, review_scope, search_limit, ledger)

        if report:
            st.subheader("📊 Final Literature Synthesis")
            st.markdown(report)
            st.divider()
            st.subheader("📜 Research Ledger")
            st.json(ledger)