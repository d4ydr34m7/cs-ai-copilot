import logging

from openai import OpenAI, OpenAIError

from app.llm_client import MODEL, openai_client
from app.schemas import SOPDraft

log = logging.getLogger(__name__)

SOP_MAX_TOKENS = 2048


def sop_prompt(chat_log: str, signals_block: str) -> str:
    return f"""You turn a Slack-style incident transcript into a structured SOP. Output must match the JSON schema only.

Hard rules:
- root_cause: ONE sentence, true root cause (not symptoms). If unclear: "Unknown".
- services_involved: names/strings copied from the transcript only. If none identifiable: ["Unknown"].
- evidence: exact quoted phrases or lines copied from the transcript that support root_cause. If none: ["Unknown"].
- No invented services, metrics, or events. If unsure, use "Unknown".
- markdown_content must follow this template exactly (no extra sections, no preamble):

# <Short Title>

## Symptoms
- bullet points only

## Root Cause
<one sentence>

## Resolution Steps
1. First step (numbered list: 1. 2. 3.)
2. Next step

## Affected Services
- list services mentioned in transcript, or "Unknown"

Known Signals (heuristic; do not treat as facts—only transcript text counts):
{signals_block}

Transcript:
---
{chat_log}
---
"""


def call_openai_sop(client: OpenAI, prompt: str) -> SOPDraft | None:
    resp = client.beta.chat.completions.parse(
        model=MODEL,
        temperature=0,
        max_tokens=SOP_MAX_TOKENS,
        messages=[
            {
                "role": "system",
                "content": "SOP extractor; transcript-only facts; schema must validate.",
            },
            {"role": "user", "content": prompt},
        ],
        response_format=SOPDraft,
    )
    return resp.choices[0].message.parsed


def sop_with_openai(chat_log: str, signals_block: str) -> SOPDraft | None:
    client = openai_client()
    if client is None:
        return None
    try:
        return call_openai_sop(client, sop_prompt(chat_log, signals_block))
    except OpenAIError:
        log.exception("openai sop failed chat_len=%d", len(chat_log))
        return None
