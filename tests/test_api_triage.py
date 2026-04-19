from app.schemas import TriageDecision
from app.triage_service import fallback_decision
from tests.fixtures import (
    API_TIMEOUT_STAGING,
    CRITICAL_DB_PRODUCTION,
    INFRA_CPU_SPIKE,
    NOISY_LOW_SEVERITY,
)


def test_post_triage_critical_db(client, monkeypatch, stub_openai_client):
    want = TriageDecision(
        severity="High",
        category="Database Error",
        tldr="Prod Oracle pool exhausted.",
        route_to="Data Engineering",
    )
    monkeypatch.setattr("app.llm_client.call_openai_triage", lambda _c, _p: want)
    res = client.post("/triage", json=CRITICAL_DB_PRODUCTION)
    assert res.status_code == 200
    assert res.json() == want.model_dump()


def test_post_triage_timeout(client, monkeypatch, stub_openai_client):
    want = TriageDecision(
        severity="Medium",
        category="API Timeout",
        tldr="Gateway timeout on payments.",
        route_to="Backend",
    )
    monkeypatch.setattr("app.llm_client.call_openai_triage", lambda _c, _p: want)
    res = client.post("/triage", json=API_TIMEOUT_STAGING)
    assert res.status_code == 200
    body = res.json()
    assert body["category"] == "API Timeout"
    assert body["route_to"] == "Backend"


def test_post_triage_runtime_error_fallback(client, monkeypatch, stub_openai_client):
    def boom(_c, _p):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.llm_client.call_openai_triage", boom)
    res = client.post("/triage", json=INFRA_CPU_SPIKE)
    assert res.status_code == 200
    assert res.json() == fallback_decision().model_dump()


def test_bad_tags_422(client):
    bad = {**NOISY_LOW_SEVERITY, "tags": ["not-a-datadog-tag"]}
    assert client.post("/triage", json=bad).status_code == 422


def test_no_api_key_fallback(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("app.llm_client.openai_client", lambda: None)
    res = client.post("/triage", json=CRITICAL_DB_PRODUCTION)
    assert res.status_code == 200
    assert res.json() == fallback_decision().model_dump()
