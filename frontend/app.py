import streamlit as st
import requests
import time
import json

SOP_API_URL = "http://127.0.0.1:8000/generate-sop"
TRIAGE_API_URL = "http://127.0.0.1:8000/triage"

# --- MOCK DATA ---

SAMPLE_TRANSCRIPTS = {
    "CASE-84291: Wire-to-Core Reconciliation Failure": """System: Case assigned to Queue: Tier 2 Support
Sarah (CS): Hey team, the wire-to-core reconciliation is failing this morning. The scorecards are coming up completely blank for the overnight batch. Clients are going to be asking for these reports in about 2 hours.
Alex (DevEng): Looking into it now. I'm pulling up the Datadog logs for the wire-to-core pipeline to see where it stopped.
Alex (DevEng): Okay, I see the issue. The pipeline timed out because the Oracle DB was completely locked. It couldn't execute the read queries. Let me check what else was running at 3:00 AM.
Alex (DevEng): Found it. Looks like the nightly stale data cleaner job hung up. It opened a transaction on the core transaction table but never committed, keeping a lock on the whole table.
Sarah (CS): Yikes. Can we fix it so the clients get their reports today? Let me know if I need to send out a delay communication.
Alex (DevEng): No comms needed yet. I just SSH'd in, force-killed the hung cleaner job, and manually re-triggered the wire-to-core pipeline. It's processing the 45,000 records now. Should take about 10 mins.
Sarah (CS): Awesome, I see the scorecards updating on my end. What's the long-term fix so this doesn't happen tomorrow?
Alex (DevEng): I'll write a Jira ticket for the next sprint to add a 15-minute timeout to the data cleaner cron job. That way, if it hangs again, it automatically fails instead of locking the table indefinitely.""",
    
    "CASE-84292: 504 Gateway Timeout (Prod)": """System: Status changed from New to In Progress. SLA timer started.
Sarah (CS): Urgent: Multiple clients are reporting they cannot log in. They are getting 504 Gateway Timeout errors on the main authentication portal.
System: Escalated to P1. Paged On-Call Engineer.
Alex (DevEng): Checking AWS CloudWatch now. The auth-gateway instances are healthy, but they can't reach the backend.
Alex (DevEng): Ah, it's the Redis cache. It hit its memory limit (OOM) and crashed, so all the session token lookups are hanging. I just flushed the stale keys from the cache to restore service. Logins should be working again.
Sarah (CS): Confirming logins are working. Thanks for the quick fix. Do we need to upgrade the cache size?
Alex (DevEng): Yeah, we've onboarded a lot of users this month. I just opened a PR to bump the maxmemory config from 2GB to 4GB in the terraform infrastructure file. Merging it today.
System: Case Status changed to Resolved.""",
    
    "CASE-84293: TechCorp Admin Password Reset": """Sarah (CS): Hi team, the client admin for TechCorp forgot their password and they are locked out of the portal. Because they are the only admin, they can't trigger the reset themselves. Can someone send the reset link manually?
System: Assigned to DevQueue.
Alex (DevEng): Done. I triggered the manual reset script. The link has been sent to their registered admin email.
Sarah (CS): Thanks! They confirmed they got it and are back in. Closing case."""
}

SAMPLE_ALERTS = {
    "Datadog: Prod Database CPU Lock": {
        "monitor_id": "mon-prod-oracle-01",
        "status": "Alert",
        "title": "CRITICAL: Oracle DB CPU > 99%",
        "tags": ["env:production", "service:database", "team:data-eng"],
        "event_msg": "CPU utilization on prod-oracle-primary has been over 99% for 5 minutes. Active queries are queuing.",
        "timestamp": int(time.time())
    },
    "Datadog: Payment API Latency": {
        "monitor_id": "mon-payment-api-04",
        "status": "Warning",
        "title": "Elevated Latency on Stripe Webhook",
        "tags": ["env:staging", "service:payments", "type:api"],
        "event_msg": "p99 latency is currently at 1200ms. Threshold is 1000ms. Not impacting prod transactions yet.",
        "timestamp": int(time.time())
    }
}

# --- UI COMPONENTS ---

def render_header():
    st.set_page_config(page_title="Engineering Co-Pilot", layout="wide")
    st.title("Enterprise Engineering Co-Pilot")
    st.markdown("Automated Alert Triage and Root Cause SOP Generation.")
    st.divider()

def render_sidebar():
    st.sidebar.markdown("### Nasdaq Cloud Platform")
    st.sidebar.caption("Internal Developer Tooling")
    st.sidebar.divider()
    
    st.sidebar.markdown("**System Status**")
    st.sidebar.success("FastAPI Microservice: Online")
    st.sidebar.caption("Architecture: Event-Driven")
    st.sidebar.caption("Model: GPT-4o-Mini")
    st.sidebar.caption("Validation: Strict Pydantic")

# --- API CALLS ---

def generate_sop(chat_log: str):
    try:
        response = requests.post(SOP_API_URL, json={"chat_log": chat_log})
        if response.status_code == 200:
            return response.json()
        return {"error": f"{response.status_code} - {response.text}"}
    except requests.exceptions.ConnectionError:
        return {"error": "Could not connect to backend."}

def triage_alert(alert_payload: dict):
    try:
        response = requests.post(TRIAGE_API_URL, json=alert_payload)
        if response.status_code == 200:
            return response.json()
        return {"error": f"{response.status_code} - {response.text}"}
    except requests.exceptions.ConnectionError:
        return {"error": "Could not connect to backend."}

# --- MAIN APP ---

def main():
    render_header()
    render_sidebar()
    
    # Create the Tabs
    tab1, tab2 = st.tabs(["🚦 Incident Triage Engine", "📄 Post-Incident SOP Generator"])
    
    # --- TAB 1: TRIAGE ---
    with tab1:
        st.markdown("### Incoming Monitoring Alerts")
        st.caption("Simulates catching raw JSON webhooks from Datadog and using AI to route them.")
        
        t_col1, t_col2 = st.columns(2, gap="large")
        
        with t_col1:
            selected_alert_name = st.selectbox("Select a mock Datadog alert:", list(SAMPLE_ALERTS.keys()))
            selected_alert_data = SAMPLE_ALERTS[selected_alert_name]
            
            st.json(selected_alert_data)
            triage_btn = st.button("Run AI Triage", type="primary", use_container_width=True)
            
        with t_col2:
            st.subheader("Triage Decision")
            if triage_btn:
                with st.spinner("Classifying alert and determining routing..."):
                    result = triage_alert(selected_alert_data)
                    
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.success("Triage Complete")
                        
                        m1, m2 = st.columns(2)
                        
                        # Color code severity
                        sev = result.get("severity", "Unknown")
                        sev_color = "red" if sev == "High" else "orange" if sev == "Medium" else "green"
                        m1.markdown(f"**Severity:** :{sev_color}[{sev}]")
                        
                        m2.markdown(f"**Category:** {result.get('category')}")
                        
                        st.divider()
                        st.markdown(f"**TL;DR for On-Call:**\n> {result.get('tldr')}")
                        
                        st.info(f"**Action:** Automatically routing to Jira queue: `{result.get('route_to')}`")
            else:
                st.info("Click 'Run AI Triage' to process the incoming payload.")

    # --- TAB 2: SOP ---
    with tab2:
        st.markdown("### Support Queue Resolution")
        st.caption("Simulates closing a Salesforce case and generating internal documentation.")
        
        s_col1, s_col2 = st.columns(2, gap="large")
        
        with s_col1:
            selected_scenario = st.selectbox("Search Case ID or select from queue:", list(SAMPLE_TRANSCRIPTS.keys()))
            transcript_input = st.text_area(
                "Transcript Input",
                value=SAMPLE_TRANSCRIPTS[selected_scenario],
                height=400,
                label_visibility="collapsed"
            )
            generate_btn = st.button("Generate Draft SOP", type="primary", use_container_width=True)
            
        with s_col2:
            st.subheader("Knowledge Base Draft")
            if generate_btn:
                with st.spinner("Analyzing transcript and extracting root cause..."):
                    result = generate_sop(transcript_input)
                    
                    if result and "error" not in result:
                        if result.get("confidence") == "Low":
                            st.warning("System flagged this transcript with LOW confidence. No technical root cause was found, or the issue is trivial.")
                            st.info(f"Fallback Message: {result.get('markdown_content')}")
                        else:
                            # 1. Top Metrics
                            m1, m2 = st.columns(2)
                            m1.metric("Confidence Score", result.get("confidence", "High"))
                            
                            services = result.get("services_involved", [])
                            valid_services = [s for s in services if s != "Unknown"]
                            m2.metric("Services Impacted", len(valid_services))
                            
                            # 2. Provenance / Evidence Expander
                            evidence = result.get("evidence", [])
                            valid_evidence = [e for e in evidence if e != "Unknown"]
                            
                            if valid_evidence:
                                with st.expander("  View Audit Trail"):
                                    st.markdown("The following quotes were deterministically extracted from the transcript to justify this root cause:")
                                    for quote in valid_evidence:
                                        st.caption(f"> *\"{quote}\"*")
                            
                            st.divider()
                            
                            # 3. The Markdown Article
                            with st.container(border=True):
                                st.markdown(result.get("markdown_content"))
                    else:
                        st.error(result.get("error", "Unknown Error"))
            else:
                st.info("Select a case from the queue and click 'Generate Draft SOP' to begin analysis.")
if __name__ == "__main__":
    main()