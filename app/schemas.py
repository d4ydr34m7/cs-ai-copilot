from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Severity = Literal["High", "Medium", "Low"]
Category = Literal["Database Error", "API Timeout", "Infra Issue", "Unknown"]
RouteTo = Literal["Data Engineering", "Backend", "Infra", "SRE"]

SOPConfidence = Literal["High", "Medium", "Low"]


class IncomingAlert(BaseModel):
    monitor_id: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    tags: list[str] = Field(..., min_length=1)
    event_msg: str = Field(..., min_length=1)
    timestamp: int

    @field_validator("monitor_id", "status", "title", "event_msg", mode="before")
    @classmethod
    def _strip_text(cls, v):
        if not isinstance(v, str):
            raise TypeError("expected a string")
        v = v.strip()
        if not v:
            raise ValueError("can't be blank")
        return v

    @field_validator("tags", mode="before")
    @classmethod
    def _tags(cls, v):
        if not isinstance(v, list):
            raise TypeError("tags must be a list")
        cleaned = []
        for i, raw in enumerate(v):
            if not isinstance(raw, str):
                raise TypeError(f"tag {i} must be a string")
            t = raw.strip()
            if not t:
                raise ValueError(f"tag {i} is empty")
            if ":" not in t:
                raise ValueError(f"tag {i} should look like key:value, got {raw!r}")
            cleaned.append(t)
        return cleaned


class TriageDecision(BaseModel):
    severity: Severity
    category: Category
    tldr: str = Field(..., min_length=1, max_length=500)
    route_to: RouteTo


class TranscriptPayload(BaseModel):
    chat_log: str

    @field_validator("chat_log", mode="before")
    @classmethod
    def _chat_log(cls, v):
        if not isinstance(v, str):
            raise TypeError("expected a string")
        v = v.strip()
        if not v:
            raise ValueError("can't be empty")
        return v


def make_sop_id(root_cause: str, services: list[str]) -> str:
    key = root_cause.strip() + "|" + "|".join(sorted(s.strip() for s in services))
    return sha256(key.encode("utf-8")).hexdigest()[:32]


class SOPDraft(BaseModel):
    """LLM structured output only — no sop_id/confidence (computed server-side)."""

    root_cause: str = Field(..., min_length=1, max_length=500)
    services_involved: list[str]
    evidence: list[str]
    markdown_content: str = Field(..., min_length=1)

    @field_validator("root_cause", mode="after")
    @classmethod
    def _root_one_line(cls, v: str) -> str:
        v = v.strip()
        if "\n" in v or "\r" in v:
            raise ValueError("root_cause must be a single sentence")
        return v

    @field_validator("services_involved", mode="before")
    @classmethod
    def _services(cls, v):
        if not isinstance(v, list):
            raise TypeError("services_involved must be a list")
        out = [str(x).strip() for x in v if str(x).strip()]
        if not out:
            return ["Unknown"]
        return out

    @field_validator("evidence", mode="before")
    @classmethod
    def _evidence(cls, v):
        if not isinstance(v, list):
            raise TypeError("evidence must be a list")
        out = [str(x).strip() for x in v if str(x).strip()]
        if not out:
            return ["Unknown"]
        return out


class GeneratedSOP(BaseModel):
    sop_id: str = Field(..., min_length=8, max_length=64)
    confidence: SOPConfidence
    root_cause: str = Field(..., min_length=1, max_length=500)
    services_involved: list[str]
    evidence: list[str]
    markdown_content: str = Field(..., min_length=1)

    @field_validator("root_cause", mode="after")
    @classmethod
    def _root_one_line(cls, v: str) -> str:
        v = v.strip()
        if "\n" in v or "\r" in v:
            raise ValueError("root_cause must be a single sentence")
        return v

    @field_validator("services_involved", mode="before")
    @classmethod
    def _services(cls, v):
        if not isinstance(v, list):
            raise TypeError("services_involved must be a list")
        out = [str(x).strip() for x in v if str(x).strip()]
        if not out:
            return ["Unknown"]
        return out

    @field_validator("evidence", mode="before")
    @classmethod
    def _evidence(cls, v):
        if not isinstance(v, list):
            raise TypeError("evidence must be a list")
        out = [str(x).strip() for x in v if str(x).strip()]
        if not out:
            return ["Unknown"]
        return out


# --- SALESFORCE MOCK SCHEMAS ---

class CaseComment(BaseModel):
    CreatedBy: str = Field(..., min_length=1)
    Body: str = Field(..., min_length=1)

class SalesforceCasePayload(BaseModel):
    CaseId: str = Field(..., min_length=1)
    Subject: str = Field(..., min_length=1)
    Status: str = Field(..., min_length=1)
    CaseComments: list[CaseComment]