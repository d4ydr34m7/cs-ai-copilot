from openai import OpenAIError

from app.schemas import GeneratedSOP, SOPDraft, TranscriptPayload, make_sop_id
from app.sop_service import fallback_sop, generate_sop, sop_grounded
from tests.sop_fixtures import VALID_LOG, VALID_MARKDOWN


def _valid_draft():
    return SOPDraft(
        root_cause="Connection pool exhaustion caused refused connections during the spike.",
        services_involved=["payments-api"],
        evidence=["connection refused to payments-api"],
        markdown_content=VALID_MARKDOWN,
    )


def test_generate_sop_happy_path(monkeypatch, stub_openai_client):
    draft = _valid_draft()
    monkeypatch.setattr("app.sop_service.sop_with_openai", lambda _log, _sig: draft)
    out = generate_sop(TranscriptPayload(chat_log=VALID_LOG))
    assert isinstance(out, GeneratedSOP)
    assert out.root_cause == draft.root_cause
    assert "payments-api" in out.services_involved
    assert out.confidence == "High"
    assert len(out.sop_id) == 32
    assert out.sop_id == make_sop_id(out.root_cause, out.services_involved)


def test_hallucinated_service_rejected(monkeypatch, stub_openai_client):
    bad = _valid_draft().model_copy(
        update={"services_involved": ["not-in-transcript-service"]}
    )
    monkeypatch.setattr("app.sop_service.sop_with_openai", lambda _log, _sig: bad)
    out = generate_sop(TranscriptPayload(chat_log=VALID_LOG))
    fb = fallback_sop()
    assert out.root_cause == fb.root_cause
    assert out.confidence == "Low"
    assert out.services_involved == ["Unknown"]


def test_openai_failure_fallback(monkeypatch, stub_openai_client):
    def boom(_log, _sig):
        raise OpenAIError("down")

    monkeypatch.setattr("app.sop_service.sop_with_openai", boom)
    out = generate_sop(TranscriptPayload(chat_log=VALID_LOG))
    assert out.confidence == "Low"
    assert "Unable to determine" in out.root_cause


def test_openai_returns_none_fallback(monkeypatch, stub_openai_client):
    monkeypatch.setattr("app.sop_service.sop_with_openai", lambda _log, _sig: None)
    out = generate_sop(TranscriptPayload(chat_log=VALID_LOG))
    assert out == fallback_sop()


def test_sop_id_stable():
    d = _valid_draft()
    a = make_sop_id(d.root_cause, d.services_involved)
    b = make_sop_id(d.root_cause, d.services_involved)
    assert a == b


def test_grounding_passes_for_valid_draft():
    assert sop_grounded(_valid_draft(), VALID_LOG) is True


def test_bad_markdown_numbering_fails(monkeypatch, stub_openai_client):
    bad_md = """# Payments API outage

## Symptoms
- Timeouts

## Root Cause
Pool exhaustion.

## Resolution Steps
Unnumbered prose only — no leading digits on lines.

## Affected Services
- payments-api
"""
    d = _valid_draft().model_copy(update={"markdown_content": bad_md})
    monkeypatch.setattr("app.sop_service.sop_with_openai", lambda _log, _sig: d)
    out = generate_sop(TranscriptPayload(chat_log=VALID_LOG))
    assert out.confidence == "Low"
