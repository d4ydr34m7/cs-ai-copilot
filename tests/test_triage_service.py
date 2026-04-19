from openai import OpenAIError

from app.schemas import IncomingAlert, TriageDecision
from app.triage_service import fallback_decision, triage
from tests.fixtures import (
    API_TIMEOUT_STAGING,
    CRITICAL_DB_PRODUCTION,
    INFRA_CPU_SPIKE,
    NOISY_LOW_SEVERITY,
)


def test_critical_prod_db(monkeypatch, stub_openai_client, critical_db_production_alert):
    def fake_llm(_client, prompt: str):
        assert "CRITICAL" in prompt and "env:production" in prompt
        assert "Oracle" in prompt or "SQLRecoverableException" in prompt
        return TriageDecision(
            severity="High",
            category="Database Error",
            tldr="Prod Oracle connectivity failure; escalate data eng.",
            route_to="Data Engineering",
        )

    monkeypatch.setattr("app.llm_client.call_openai_triage", fake_llm)
    got = triage(critical_db_production_alert)
    assert got.severity == "High"
    assert got.category == "Database Error"
    assert got.route_to == "Data Engineering"


def test_api_timeout_staging(monkeypatch, stub_openai_client, api_timeout_staging_alert):
    def fake_llm(_client, prompt: str):
        assert "deadline exceeded" in prompt.lower() or "timeout" in prompt.lower()
        return TriageDecision(
            severity="Medium",
            category="API Timeout",
            tldr="Staging payments client timed out calling transfers.",
            route_to="Backend",
        )

    monkeypatch.setattr("app.llm_client.call_openai_triage", fake_llm)
    got = triage(api_timeout_staging_alert)
    assert got.category == "API Timeout"
    assert got.route_to == "Backend"
    assert got.severity == "Medium"


def test_infra_cpu(monkeypatch, stub_openai_client, infra_cpu_spike_alert):
    def fake_llm(_client, prompt: str):
        assert "cpu" in prompt.lower() or "Kubernetes" in prompt
        return TriageDecision(
            severity="Medium",
            category="Infra Issue",
            tldr="Prod node CPU sustained high; infra should drain or scale.",
            route_to="Infra",
        )

    monkeypatch.setattr("app.llm_client.call_openai_triage", fake_llm)
    got = triage(infra_cpu_spike_alert)
    assert got.category == "Infra Issue"
    assert got.route_to == "Infra"


def test_noisy_synthetic(monkeypatch, stub_openai_client, noisy_low_severity_alert):
    def fake_llm(_client, prompt: str):
        assert "Recovered" in prompt or "Synthetic" in prompt
        return TriageDecision(
            severity="Low",
            category="Unknown",
            tldr="Synthetic recovered on staging; no action.",
            route_to="SRE",
        )

    monkeypatch.setattr("app.llm_client.call_openai_triage", fake_llm)
    got = triage(noisy_low_severity_alert)
    assert got.severity == "Low"
    assert got.category == "Unknown"


def test_openai_error_falls_back(monkeypatch, stub_openai_client, critical_db_production_alert):
    def boom(_client, _prompt):
        raise OpenAIError("simulated outage")

    monkeypatch.setattr("app.llm_client.call_openai_triage", boom)
    assert triage(critical_db_production_alert) == fallback_decision()


def test_none_parse_falls_back(monkeypatch, stub_openai_client, critical_db_production_alert):
    monkeypatch.setattr("app.llm_client.call_openai_triage", lambda _c, _p: None)
    got = triage(critical_db_production_alert)
    assert got.severity == "Medium"
    assert got.category == "Unknown"
    assert got.route_to == "SRE"
    assert got.tldr == fallback_decision().tldr


def test_sample_payloads_parse():
    for row in (
        CRITICAL_DB_PRODUCTION,
        API_TIMEOUT_STAGING,
        INFRA_CPU_SPIKE,
        NOISY_LOW_SEVERITY,
    ):
        IncomingAlert.model_validate(row)
