import logging
import os
import re

from app.schemas import GeneratedSOP, SOPDraft, SOPConfidence, TranscriptPayload, make_sop_id
from app.sop_llm import sop_with_openai
from app.sop_store import save_or_reuse

log = logging.getLogger(__name__)

_KEYWORDS = ("timeout", "sql", "cpu", "restart", "error", "oom", "latency", "500")

_K8S_HOST = re.compile(
    r"\b[\w.-]+\.svc\.[\w.-]+\b|\b[\w.-]+\.(?:local|internal)\b", re.I
)
_BACKTICK = re.compile(r"`([^`\n]{1,120})`")
_SVC_KV = re.compile(r"(?:service|svc)\s*[:=]\s*([\w.-]{2,80})", re.I)
_SLACK_PIPE = re.compile(r"\|([\w.-]{2,80})>")
_HYPHEN_TOKEN = re.compile(r"\b[a-z][a-z0-9]*(?:-[a-z0-9]{2,})+\b", re.I)
_URL_HOST = re.compile(r"https?://([^/\s?#]+)", re.I)


def _known_services_from_env() -> frozenset[str]:
    raw = os.getenv("SOP_KNOWN_SERVICES", "")
    if not raw.strip():
        return frozenset()
    return frozenset(x.strip() for x in raw.split(",") if x.strip())


def extract_signals(chat_log: str) -> str:
    lower = chat_log.lower()
    kw_hits = [k for k in _KEYWORDS if k in lower]

    candidates: list[str] = []
    seen: set[str] = set()

    def add(s: str) -> None:
        s = s.strip()
        if len(s) < 2 or s in seen:
            return
        seen.add(s)
        candidates.append(s)

    for m in _BACKTICK.finditer(chat_log):
        add(m.group(1))
    for m in _SVC_KV.finditer(chat_log):
        add(m.group(1))
    for m in _SLACK_PIPE.finditer(chat_log):
        add(m.group(1))
    for m in _HYPHEN_TOKEN.finditer(chat_log):
        tok = m.group(0)
        if len(tok) >= 4:
            add(tok)
    for m in _K8S_HOST.finditer(chat_log):
        add(m.group(0))
    for m in _URL_HOST.finditer(chat_log):
        host = m.group(1).split(":")[0]
        if len(host) >= 2:
            add(host)

    catalog = _known_services_from_env()
    catalog_hits: list[str] = []
    if catalog:
        ll = chat_log.lower()
        for name in sorted(catalog):
            if name.lower() in ll:
                catalog_hits.append(name)

    lines = []
    if kw_hits:
        lines.append("Keywords: " + ", ".join(sorted(set(kw_hits))))
    else:
        lines.append("Keywords: (none)")
    if candidates:
        lines.append("Candidates: " + ", ".join(candidates[:30]))
    else:
        lines.append("Candidates: (none)")
    if catalog_hits:
        lines.append("Catalog matches (name appears in transcript): " + ", ".join(catalog_hits[:30]))
    else:
        lines.append("Catalog matches: (none)")

    return "\n".join(lines)


def _service_in_transcript(service: str, chat_log: str) -> bool:
    if service.strip() == "Unknown":
        return True
    if service in chat_log:
        return True
    return service.lower() in chat_log.lower()


def _evidence_loosely_anchored(evidence: str, chat_log: str) -> bool:
    if evidence.strip() == "Unknown":
        return True
    e = evidence.strip()
    cl = chat_log.lower()
    el = e.lower()
    if el in cl:
        return True
    norm_ev = re.sub(r"\s+", " ", el)
    norm_log = re.sub(r"\s+", " ", cl)
    if norm_ev in norm_log:
        return True
    words = [w for w in re.findall(r"[a-z0-9]+", el) if len(w) > 2]
    if not words:
        return True
    hits = sum(1 for w in words if w in cl)
    return hits >= max(1, int(len(words) * 0.4))


def resolution_steps_numbered(md: str) -> bool:
    m = re.search(
        r"##\s*Resolution Steps\s*\r?\n(.*?)(?=\r?\n## |\Z)",
        md,
        flags=re.DOTALL | re.I,
    )
    if not m:
        return False
    body = m.group(1).strip()
    if not body:
        return False
    return bool(re.search(r"(?m)^\s*\d+[\.)]\s+\S", body))


def markdown_shape_ok(md: str) -> bool:
    if not md or not md.strip():
        return False
    low = md.lower()
    for part in (
        "## symptoms",
        "## root cause",
        "## resolution steps",
        "## affected services",
    ):
        if part not in low:
            log.warning("sop validation missing section %s", part)
            return False
    if not md.lstrip().startswith("#"):
        return False
    if not resolution_steps_numbered(md):
        log.warning("sop validation resolution steps not numbered")
        return False
    return True


def sop_grounded(sop: SOPDraft, chat_log: str) -> bool:
    if not markdown_shape_ok(sop.markdown_content):
        log.warning("sop validation markdown shape failed")
        return False

    for svc in sop.services_involved:
        if not _service_in_transcript(svc, chat_log):
            log.warning("sop validation service not in transcript svc=%r", svc)
            return False

    for ev in sop.evidence:
        if ev.strip() != "Unknown" and not _evidence_loosely_anchored(ev, chat_log):
            log.warning(
                "sop evidence weak vs transcript (keeping response) ev=%r",
                ev[:120] + ("…" if len(ev) > 120 else ""),
            )

    return True


def compute_confidence(draft: SOPDraft, chat_log: str) -> SOPConfidence:
    rc = draft.root_cause.strip().lower()
    if rc in ("unknown",) or rc.startswith("unable to determine"):
        return "Low"

    ev_ok = [e for e in draft.evidence if e != "Unknown"]
    sv_ok = [s for s in draft.services_involved if s != "Unknown"]

    if len(ev_ok) >= 1 and len(sv_ok) >= 1 and rc != "unknown":
        return "High"
    if ev_ok or sv_ok:
        return "Medium"
    return "Low"


def _draft_to_generated(draft: SOPDraft, chat_log: str) -> GeneratedSOP:
    return GeneratedSOP(
        sop_id=make_sop_id(draft.root_cause, draft.services_involved),
        confidence=compute_confidence(draft, chat_log),
        root_cause=draft.root_cause,
        services_involved=draft.services_involved,
        evidence=draft.evidence,
        markdown_content=draft.markdown_content,
    )


def fallback_sop() -> GeneratedSOP:
    root = "Unable to determine root cause"
    sv = ["Unknown"]
    return GeneratedSOP(
        sop_id=make_sop_id(root, sv),
        confidence="Low",
        root_cause=root,
        services_involved=sv,
        evidence=["Unknown"],
        markdown_content="SOP generation failed. Please review manually.",
    )


def generate_sop(payload: TranscriptPayload) -> GeneratedSOP:
    text = payload.chat_log
    log.info("sop request chat_log_len=%d", len(text))

    signals = extract_signals(text)
    log.info("sop signals %s", signals.replace("\n", " | "))

    result: SOPDraft | None = None
    try:
        result = sop_with_openai(text, signals)
    except Exception:
        log.exception("sop blew up chat_log_len=%d", len(text))

    if result is None:
        log.warning("sop fallback reason=no_model_response chat_log_len=%d", len(text))
        return fallback_sop()

    if not sop_grounded(result, text):
        log.warning("sop fallback reason=validation_failed chat_log_len=%d", len(text))
        return fallback_sop()

    out = _draft_to_generated(result, text)
    stored, reused = save_or_reuse(out)
    if reused:
        log.info(
            "sop dedup reused sop_id=%s chat_log_len=%d",
            stored.sop_id[:12],
            len(text),
        )
    else:
        log.info(
            "sop stored new sop_id=%s chat_log_len=%d",
            stored.sop_id[:12],
            len(text),
        )
    log.info(
        "sop ok chat_log_len=%d sop_id=%s confidence=%s services=%d root=%s",
        len(text),
        stored.sop_id[:12],
        stored.confidence,
        len(stored.services_involved),
        (stored.root_cause[:80] + "…") if len(stored.root_cause) > 80 else stored.root_cause,
    )
    return stored
