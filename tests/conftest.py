from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.schemas import IncomingAlert
from app.sop_store import clear_store
from tests.fixtures import (
    API_TIMEOUT_STAGING,
    CRITICAL_DB_PRODUCTION,
    INFRA_CPU_SPIKE,
    NOISY_LOW_SEVERITY,
)


@pytest.fixture(autouse=True)
def _reset_sop_store():
    clear_store()
    yield
    clear_store()


@pytest.fixture
def critical_db_production_alert():
    return IncomingAlert.model_validate(CRITICAL_DB_PRODUCTION)


@pytest.fixture
def api_timeout_staging_alert():
    return IncomingAlert.model_validate(API_TIMEOUT_STAGING)


@pytest.fixture
def infra_cpu_spike_alert():
    return IncomingAlert.model_validate(INFRA_CPU_SPIKE)


@pytest.fixture
def noisy_low_severity_alert():
    return IncomingAlert.model_validate(NOISY_LOW_SEVERITY)


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


@pytest.fixture
def stub_openai_client(monkeypatch):
    monkeypatch.setattr("app.llm_client.openai_client", lambda: MagicMock())
