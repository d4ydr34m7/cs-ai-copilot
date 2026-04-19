import requests
import json
import sys

URL = "http://127.0.0.1:8000/webhooks/salesforce/case-closed"

PAYLOAD_HAPPY_PATH = {
  "CaseId": "5008c00001GxyzT",
  "Subject": "Reconciliation Failure - Wire to Core",
  "Status": "Closed",
  "CaseComments": [
    {"CreatedBy": "System", "Body": "Case assigned to Queue: Tier 2 Support"},
    {"CreatedBy": "Sarah (CS)", "Body": "Hey team, the wire-to-core reconciliation is failing this morning. The scorecards are coming up completely blank for the overnight batch. Clients are going to be asking for these reports in about 2 hours."},
    {"CreatedBy": "Alex (DevEng)", "Body": "Looking into it now. I'm pulling up the Datadog logs for the wire-to-core pipeline to see where it stopped."},
    {"CreatedBy": "Alex (DevEng)", "Body": "Okay, I see the issue. The pipeline timed out because the Oracle DB was completely locked. It couldn't execute the read queries. Let me check what else was running at 3:00 AM."},
    {"CreatedBy": "Alex (DevEng)", "Body": "Found it. Looks like the nightly stale data cleaner job hung up. It opened a transaction on the core transaction table but never committed, keeping a lock on the whole table."},
    {"CreatedBy": "Sarah (CS)", "Body": "Yikes. Can we fix it so the clients get their reports today? Let me know if I need to send out a delay communication."},
    {"CreatedBy": "Alex (DevEng)", "Body": "No comms needed yet. I just SSH'd in, force-killed the hung cleaner job, and manually re-triggered the wire-to-core pipeline. It's processing the 45,000 records now. Should take about 10 mins."},
    {"CreatedBy": "Sarah (CS)", "Body": "Awesome, I see the scorecards updating on my end. What's the long-term fix so this doesn't happen tomorrow?"},
    {"CreatedBy": "Alex (DevEng)", "Body": "I'll write a Jira ticket for the next sprint to add a 15-minute timeout to the data cleaner cron job. That way, if it hangs again, it automatically fails instead of locking the table indefinitely."}
  ]
}

PAYLOAD_SYSTEM_NOISE = {
  "CaseId": "5008c00001HtyzA",
  "Subject": "Login timeout in Prod (504 Errors)",
  "Status": "Closed",
  "CaseComments": [
    {"CreatedBy": "System", "Body": "Status changed from New to In Progress. SLA timer started."},
    {"CreatedBy": "Sarah (CS)", "Body": "Urgent: Multiple clients are reporting they cannot log in. They are getting 504 Gateway Timeout errors on the main authentication portal.\n\n---\nSarah Jenkins\nCustomer Success Manager\nNasdaq\nHalifax, NS"},
    {"CreatedBy": "System", "Body": "Escalated to P1. Paged On-Call Engineer."},
    {"CreatedBy": "Alex (DevEng)", "Body": "Checking AWS CloudWatch now. The auth-gateway instances are healthy, but they can't reach the backend."},
    {"CreatedBy": "Alex (DevEng)", "Body": "Ah, it's the Redis cache. It hit its memory limit (OOM) and crashed, so all the session token lookups are hanging. I just flushed the stale keys from the cache to restore service. Logins should be working again."},
    {"CreatedBy": "Sarah (CS)", "Body": "Confirming logins are working. Thanks for the quick fix. Do we need to upgrade the cache size?"},
    {"CreatedBy": "Alex (DevEng)", "Body": "Yeah, we've onboarded a lot of users this month. I just opened a PR to bump the maxmemory config from 2GB to 4GB in the terraform infrastructure file. Merging it today."},
    {"CreatedBy": "System", "Body": "Case Status changed to Resolved."}
  ]
}

PAYLOAD_USELESS_TICKET = {
  "CaseId": "5008c00001Jklop",
  "Subject": "Password Reset Help - Admin Locked Out",
  "Status": "Closed",
  "CaseComments": [
    {"CreatedBy": "Sarah (CS)", "Body": "Hi team, the client admin for TechCorp forgot their password and they are locked out of the portal. Because they are the only admin, they can't trigger the reset themselves. Can someone send the reset link manually?"},
    {"CreatedBy": "System", "Body": "Assigned to DevQueue."},
    {"CreatedBy": "Alex (DevEng)", "Body": "Done. I triggered the manual reset script. The link has been sent to their registered admin email."},
    {"CreatedBy": "Sarah (CS)", "Body": "Thanks! They confirmed they got it and are back in. Closing case."}
  ]
}

def run():
    print("Select a Salesforce Case to simulate closing:")
    print("1: Happy Path (Wire to Core DB Lock)")
    print("2: System Noise (Redis Cache OOM)")
    print("3: Useless Ticket (Password Reset)")
    
    choice = input("\nEnter 1, 2, or 3: ")
    
    if choice == '1':
        payload = PAYLOAD_HAPPY_PATH
    elif choice == '2':
        payload = PAYLOAD_SYSTEM_NOISE
    elif choice == '3':
        payload = PAYLOAD_USELESS_TICKET
    else:
        print("Invalid choice.")
        sys.exit(1)

    print(f"\nFiring webhook to {URL}...")
    try:
        response = requests.post(URL, json=payload)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except requests.exceptions.ConnectionError:
        print("[Error] Could not connect to FastAPI server. Is it running?")

if __name__ == "__main__":
    run()