import logging

from app.llm_client import triage_with_openai
from app.schemas import IncomingAlert, TriageDecision

log = logging.getLogger(__name__)

FALLBACK_TLDR = (
    "Automated triage did not return a result; please review with SRE."
)


def fallback_decision() -> TriageDecision:
    return TriageDecision(
        severity="Medium",
        category="Unknown",
        tldr=FALLBACK_TLDR,
        route_to="SRE",
    )


def triage(alert: IncomingAlert) -> TriageDecision:
    log.info(
        "alert in monitor=%s status=%s tags=%d",
        alert.monitor_id,
        alert.status,
        len(alert.tags),
    )

    result = None
    try:
        result = triage_with_openai(alert)
    except Exception:
        log.exception("triage blew up monitor=%s", alert.monitor_id)

    if result is None:
        log.warning("triage fallback monitor=%s", alert.monitor_id)
        return fallback_decision()

    log.info(
        "triage done monitor=%s %s/%s -> %s",
        alert.monitor_id,
        result.severity,
        result.category,
        result.route_to,
    )
    return result
