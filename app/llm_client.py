import logging
import os

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

from app.schemas import IncomingAlert, TriageDecision

load_dotenv()

log = logging.getLogger(__name__)

MODEL = "gpt-4o-mini"
TIMEOUT_S = 30.0
MAX_TOKENS = 256


def openai_client() -> OpenAI | None:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        log.error("OPENAI_API_KEY not set")
        return None
    return OpenAI(api_key=key, timeout=TIMEOUT_S)


def prompt_for(alert: IncomingAlert) -> str:
    tags = ", ".join(alert.tags)
    return f"""Classify this monitoring alert. JSON schema output only.

Rules:
- severity High if title/tags say CRITICAL or tags include env:production (or prod); else Medium unless noise, then Low.
- category: Database Error for SQL/JDBC/Oracle/DB/connection issues; API Timeout for timeouts/504/gateway; Infra Issue for host/disk/CPU/OOM/network adapter/pod without DB/API angle; else Unknown.
- route_to exactly one of: Data Engineering, Backend, Infra, SRE (DE=data/warehouse, Backend=services/API, Infra=hosts/k8s/net, SRE=unclear).
- tldr: one sentence for on-call.

monitor_id: {alert.monitor_id}
status: {alert.status}
title: {alert.title}
tags: {tags}
event_msg: {alert.event_msg}
timestamp: {alert.timestamp}
"""


def call_openai_triage(client: OpenAI, prompt: str) -> TriageDecision | None:
    resp = client.beta.chat.completions.parse(
        model=MODEL,
        temperature=0,
        max_tokens=MAX_TOKENS,
        messages=[
            {
                "role": "system",
                "content": "Incident classifier; values must match the schema.",
            },
            {"role": "user", "content": prompt},
        ],
        response_format=TriageDecision,
    )
    return resp.choices[0].message.parsed


def triage_with_openai(alert: IncomingAlert) -> TriageDecision | None:
    client = openai_client()
    if client is None:
        return None
    try:
        return call_openai_triage(client, prompt_for(alert))
    except OpenAIError:
        log.exception("openai triage failed monitor=%s", alert.monitor_id)
        return None
