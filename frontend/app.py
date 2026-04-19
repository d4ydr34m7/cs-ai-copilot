import streamlit as st
import requests

API_URL = "http://127.0.0.1:8000/generate-sop"

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

def render_header():
    st.set_page_config(page_title="CS AI Co-Pilot", layout="wide")
    st.title("Enterprise CS AI Co-Pilot")
    st.markdown("Automated Root Cause Analysis and SOP Generation from Support Transcripts.")

def generate_sop(chat_log: str):
    try:
        response = requests.post(API_URL, json={"chat_log": chat_log})
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Backend API Error: {response.status_code} - {response.text}")
            return None
    except requests.exceptions.ConnectionError:
        st.error("Could not connect to the backend. Is the FastAPI server running?")
        return None

def main():
    render_header()
    
    st.sidebar.header("Test Scenarios")
    selected_scenario = st.sidebar.selectbox("Select a sample transcript:", list(SAMPLE_TRANSCRIPTS.keys()))
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Raw Slack / Case Transcript")
        transcript_input = st.text_area(
            "Edit or paste custom transcript here:",
            value=SAMPLE_TRANSCRIPTS[selected_scenario],
            height=400
        )
        
        generate_btn = st.button("Generate SOP", type="primary")
        
    with col2:
        st.subheader("Generated Knowledge Base Article")
        
        if generate_btn:
            with st.spinner("Analyzing transcript and extracting root cause..."):
                result = generate_sop(transcript_input)
                
                if result:
                    if result.get("confidence") == "Low":
                        st.warning("System flagged this transcript with LOW confidence. No technical root cause was found, or the issue is trivial.")
                        st.markdown(f"> **Fallback Message:** {result.get('markdown_content')}")
                    else:
                        st.success(f"Generated successfully. (Confidence: {result.get('confidence')})")
                        with st.container(border=True):
                            st.markdown(result.get("markdown_content"))

if __name__ == "__main__":
    main()