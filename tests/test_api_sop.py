from app.schemas import SOPDraft, make_sop_id
from app.sop_service import fallback_sop
from tests.sop_fixtures import VALID_LOG, VALID_MARKDOWN


def test_generate_sop_endpoint_ok(client, monkeypatch, stub_openai_client):
    draft = SOPDraft(
        root_cause="Connection pool exhaustion caused refused connections during the spike.",
        services_involved=["payments-api"],
        evidence=["connection refused to payments-api"],
        markdown_content=VALID_MARKDOWN,
    )
    monkeypatch.setattr("app.sop_service.sop_with_openai", lambda _log, _sig: draft)

    res = client.post("/generate-sop", json={"chat_log": VALID_LOG})
    assert res.status_code == 200
    body = res.json()
    assert body["confidence"] == "High"
    assert body["sop_id"] == make_sop_id(body["root_cause"], body["services_involved"])
    assert "payments-api" in body["services_involved"]


def test_generate_sop_fallback_on_none(client, monkeypatch, stub_openai_client):
    monkeypatch.setattr("app.sop_service.sop_with_openai", lambda _log, _sig: None)
    res = client.post("/generate-sop", json={"chat_log": VALID_LOG})
    assert res.status_code == 200
    assert res.json() == fallback_sop().model_dump()
    assert client.get("/sop/search").json() == []


def test_get_sop_404(client):
    assert client.get("/sop/" + "a" * 32).status_code == 404


def test_get_sop_after_generate(client, monkeypatch, stub_openai_client):
    draft = SOPDraft(
        root_cause="Connection pool exhaustion caused refused connections during the spike.",
        services_involved=["payments-api"],
        evidence=["connection refused to payments-api"],
        markdown_content=VALID_MARKDOWN,
    )
    monkeypatch.setattr("app.sop_service.sop_with_openai", lambda _log, _sig: draft)
    post = client.post("/generate-sop", json={"chat_log": VALID_LOG})
    sid = post.json()["sop_id"]
    got = client.get(f"/sop/{sid}")
    assert got.status_code == 200
    assert got.json() == post.json()


def test_search_sop_by_service_and_root_cause(client, monkeypatch, stub_openai_client):
    draft = SOPDraft(
        root_cause="Connection pool exhaustion caused refused connections during the spike.",
        services_involved=["payments-api"],
        evidence=["connection refused to payments-api"],
        markdown_content=VALID_MARKDOWN,
    )
    monkeypatch.setattr("app.sop_service.sop_with_openai", lambda _log, _sig: draft)
    client.post("/generate-sop", json={"chat_log": VALID_LOG})
    by_svc = client.get("/sop/search", params={"service": "payments-api"})
    assert by_svc.status_code == 200
    assert len(by_svc.json()) == 1
    by_rc = client.get("/sop/search", params={"root_cause": "pool"})
    assert len(by_rc.json()) == 1
    nomatch = client.get("/sop/search", params={"service": "zzz"})
    assert nomatch.json() == []


def test_dedup_returns_same_record(client, monkeypatch, stub_openai_client):
    draft = SOPDraft(
        root_cause="Connection pool exhaustion caused refused connections during the spike.",
        services_involved=["payments-api"],
        evidence=["connection refused to payments-api"],
        markdown_content=VALID_MARKDOWN,
    )
    monkeypatch.setattr("app.sop_service.sop_with_openai", lambda _log, _sig: draft)
    a = client.post("/generate-sop", json={"chat_log": VALID_LOG})
    b = client.post("/generate-sop", json={"chat_log": VALID_LOG})
    assert a.json()["sop_id"] == b.json()["sop_id"]
    assert client.get("/sop/search").json() == [a.json()]
