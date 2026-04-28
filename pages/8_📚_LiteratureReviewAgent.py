import streamlit as st
import json
import time
import requests
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
from mistralai.client import Mistral
import xml.etree.ElementTree as ET
import re

# --- 1. RESEARCH LEDGER ---
def init_ledger():
    return {
        "project": "L.U.M.A. PRISMA Audit",
        "timestamp_start": datetime.now().isoformat(),
        "decisions": [],
        "attrition": {"initial_found": 0, "duplicates_removed": 0, "final_included": 0}
    }

def log_to_ledger(ledger, step, decision, justification, metadata=None):
    ledger["decisions"].append({
        "timestamp": datetime.now().isoformat(),
        "prisma_step": step,
        "decision": decision,
        "justification": justification,
        "item_metadata": metadata
    })

# --- 2. SEARCH TOOLS (Hardened & Scoped) ---

def tool_elsevier_search(query_string, start_year, end_year, auth_token=None):
    url = "https://api.elsevier.com/content/search/scidir"
    headers = {"X-ELS-APIKey": st.secrets["ELSEVIER_API_KEY"], "Accept": "application/json"}
    if auth_token: headers["X-ELS-Authtoken"] = auth_token

    clean_q = re.sub(r'[\(\)\"\']', '', str(query_string))
    params = {"query": f"TITLE-ABSTR-KEY({clean_q})", "date": f"{start_year}-{end_year}", "count": 50, "view": "STANDARD"}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            entries = resp.json().get("search-results", {}).get("entry", [])
            return [{
                "title": e.get("dc:title"),
                "snippet": e.get("dc:description", "Abstract locked."),
                "link": next((l.get("@href") for l in e.get("link", []) if l.get("@rel") == "scidir"), ""),
                "source": "ScienceDirect", "doi": e.get("prism:doi")
            } for e in entries if isinstance(e, dict) and e.get("dc:title")]
    except: pass
    return []

def tool_google_scholar(query, start_year, end_year):
    params = {"engine": "google_scholar", "q": query, "api_key": st.secrets["SERP_API_KEY"], "num": 50, "as_ylo": start_year, "as_yhi": end_year}
    try:
        r = requests.get("https://serpapi.com/search.json", params=params, timeout=15).json()
        return [{"title": p['title'], "snippet": p.get('snippet', ''), "link": p.get('link'), "source": "Google Scholar", "cite_id": p.get('inline_links', {}).get('cited_by', {}).get('cites_id')} for p in r.get("organic_results", [])]
    except: pass
    return []

def tool_arxiv_search(query_string, limit=50):
    clean_q = re.sub(r'[\(\)\"\']', '', str(query_string)).strip().replace(' ', '+')
    # Use the broad search prefix for better results
    formatted_q = f"all:{clean_q.replace('+', '+all:')}"
    try:
        time.sleep(1) 
        resp = requests.get(f"http://export.arxiv.org/api/query?search_query={formatted_q}&max_results={limit}", timeout=15)
        root = ET.fromstring(resp.content)
        results = []
        for e in root.findall('{http://www.w3.org/2005/Atom}entry'):
            results.append({
                "title": e.find('{http://www.w3.org/2005/Atom}title').text.strip(),
                "snippet": e.find('{http://www.w3.org/2005/Atom}summary').text.strip(),
                "link": e.find('{http://www.w3.org/2005/Atom}id').text,
                "source": "arXiv"
            })
        return results
    except: pass
    return []

# --- 3. HARDENED AI CALL (BACKOFF PROTOCOL) ---

def safe_mistral_call(client, messages, response_format=None, max_retries=5):
    for i in range(max_retries):
        try:
            return client.chat.complete(model="mistral-large-latest", messages=messages, response_format=response_format)
        except Exception as e:
            if "429" in str(e) and i < max_retries - 1:
                wait = (i + 1) * 8
                st.toast(f"⏳ Rate Limit hit. Resting {wait}s...", icon="🧊")
                time.sleep(wait)
            else: return None

# --- 4. THE 6-STEP PRISMA PIPELINE ---

def run_prisma_review(client, topic, inc, exc, sy, ey, auth_token, ledger):
    hud = st.status("🚀 Launching PRISMA Audit Engine...", expanded=True)
    
    # 1. IDENTIFICATION
    hud.update(label="📡 Step 1: Identification")
    q_prompt = f"Topic: {topic}. Return JSON: 'scholar' (boolean), 'arxiv' (keywords), 'elsevier' (keywords)."
    q_resp = safe_mistral_call(client, [{"role": "user", "content": q_prompt}], response_format={"type":"json_object"})
    qs = json.loads(q_resp.choices[0].message.content) if q_resp else {"scholar": topic, "arxiv": topic, "elsevier": topic}
    
    e_raw = tool_elsevier_search(qs.get('elsevier'), sy, ey, auth_token) or []
    s_raw = tool_google_scholar(qs.get('scholar'), sy, ey) or []
    a_raw = tool_arxiv_search(qs.get('arxiv')) or []
    
    all_raw = e_raw + s_raw + a_raw
    ledger["attrition"]["initial_found"] = len(all_raw)
    st.write(f"📥 Found: {len(e_raw)} ScienceDirect, {len(s_raw)} Scholar, {len(a_raw)} arXiv.")

    # 2. DEDUPLICATION
    unique = []
    seen = set()
    dupes = 0
    for p in all_raw:
        norm = re.sub(r'[^a-z0-9]', '', p['title'].lower())
        if norm not in seen:
            unique.append(p); seen.add(norm)
        else: dupes += 1
    ledger["attrition"]["duplicates_removed"] = dupes
    st.write(f"🗑️ Deduplication: {dupes} removed.")

    # 3. ELIGIBILITY AUDIT
    eligible = []
    for i, p in enumerate(unique):
        st.write(f"⚖️ [{i+1}/{len(unique)}] Auditing: {p['title'][:55]}...")
        audit = safe_mistral_call(client, [
            {"role": "system", "content": f"INC: {inc}\nEXC: {exc}"},
            {"role": "user", "content": f"Title: {p['title']}\nAbstract: {p['snippet']}\nReturn JSON: {{'decision': 'Include'/'Exclude', 'justification': 'Reason', 'summary': 'Summary'}}"}
        ], response_format={"type":"json_object"})
        
        if audit:
            try:
                res = json.loads(audit.choices[0].message.content)
                decision = res.get('decision') or res.get('Decision') or "Exclude"
                log_to_ledger(ledger, "Eligibility", decision, res.get('justification', 'N/A'), metadata=p)
                if decision == "Include":
                    p['summary'] = res.get('summary'); p['justification'] = res.get('justification')
                    eligible.append(p)
            except: pass
        time.sleep(0.4)

    hud.update(label="✅ Review Complete", state="complete")
    ledger["attrition"]["final_included"] = len(eligible)
    return eligible

# --- 5. UI COMMAND CENTER ---
st.title("🔬 PRISMA Research Agent")
with st.sidebar:
    st.header("🔐 Access Control")
    auth_token = st.text_input("Elsevier AuthToken (Optional)", type="password")

with st.container(border=True):
    topic_input = st.text_input("Research Topic", value="AI in medical diagnosis")
    col1, col2 = st.columns(2)
    with col1:
        inc_input = st.text_area("Inclusion Criteria", value="Peer-reviewed frameworks.")
    with col2:
        exc_input = st.text_area("Exclusion Criteria", value="Non-English papers.")
    
    c_y1, c_y2 = st.columns(2)
    with c_y1: start_y = st.number_input("Start Year", value=2020)
    with c_y2: end_y = st.number_input("End Year", value=2026)

    if st.button("🚀 Execute Traceable Review", type="primary", use_container_width=True):
        # INITIALIZE CLIENT LOCALLY TO AVOID IMPORT ERRORS
        mistral_client = Mistral(api_key=st.secrets["MISTRAL_KEY"])
        research_ledger = init_ledger()
        
        papers = run_prisma_review(mistral_client, topic_input, inc_input, exc_input, start_y, end_y, auth_token, research_ledger)
        
        if papers:
            st.subheader("📊 PRISMA Attrition")
            st.table(pd.DataFrame({
                "Step": ["Identified", "Duplicates Removed", "Eligible"],
                "Count": [research_ledger["attrition"]["initial_found"], research_ledger["attrition"]["duplicates_removed"], len(papers)]
            }).set_index("Step"))
            
            st.subheader("📚 Final Library")
            st.dataframe(pd.DataFrame(papers)[["title", "source", "summary", "justification"]], use_container_width=True, hide_index=True)
            st.download_button("💾 Download Ledger (JSON)", json.dumps(research_ledger, indent=4), "audit_ledger.json")