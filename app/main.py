import logging

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query

from app.schemas import (
    GeneratedSOP, 
    IncomingAlert, 
    TranscriptPayload, 
    TriageDecision,
    SalesforceCasePayload
)
from app.sop_service import generate_sop as run_generate_sop
from app.sop_store import get_sop, search_sops
from app.triage_service import triage as run_triage

load_dotenv()

if not logging.root.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

log = logging.getLogger(__name__)

app = FastAPI(title="Alert Triage", version="1.0.0")


async def mock_salesforce_writeback(case_id: str, sop_id: str, markdown: str):
    """Simulates an asynchronous API call back to Salesforce Knowledge Base."""
    log.info(f"[MOCK EXTERNAL API] Successfully posted Draft SOP '{sop_id}' to Salesforce Knowledge for Case {case_id}")


@app.post("/triage", response_model=TriageDecision)
def triage(alert: IncomingAlert) -> TriageDecision:
    return run_triage(alert)


@app.post("/generate-sop", response_model=GeneratedSOP)
def generate_sop(payload: TranscriptPayload) -> GeneratedSOP:
    return run_generate_sop(payload)


@app.post("/webhooks/salesforce/case-closed", status_code=202)
async def salesforce_webhook(payload: SalesforceCasePayload, background_tasks: BackgroundTasks):
    log.info(f"Webhook received: Case {payload.CaseId} closed. Starting ingestion pipeline.")
    
    clean_chat_lines = []
    for comment in payload.CaseComments:
        if comment.CreatedBy.lower() != "system":
            clean_chat_lines.append(f"{comment.CreatedBy}: {comment.Body}")
            
    sanitized_chat_log = "\n\n".join(clean_chat_lines)
    
    try:
        transcript_payload = TranscriptPayload(chat_log=sanitized_chat_log)
        sop_result = run_generate_sop(transcript_payload)
        
        if sop_result and sop_result.confidence in ["High", "Medium"]:
            background_tasks.add_task(
                mock_salesforce_writeback, 
                payload.CaseId, 
                sop_result.sop_id, 
                sop_result.markdown_content
            )
            
    except Exception as e:
        log.error(f"SOP Generation failed during webhook processing: {e}")

    return {"status": "Processing Accepted", "case_id": payload.CaseId}


@app.get("/sop/search", response_model=list[GeneratedSOP])
def search_sop_endpoint(
    service: str | None = Query(None, description="Match if substring of a stored service"),
    root_cause: str | None = Query(
        None, description="Match if substring of stored root_cause"
    ),
) -> list[GeneratedSOP]:
    return search_sops(service, root_cause)


@app.get("/sop/{sop_id}", response_model=GeneratedSOP)
def read_sop(sop_id: str) -> GeneratedSOP:
    row = get_sop(sop_id)
    if row is None:
        raise HTTPException(status_code=404, detail="SOP not found")
    return row