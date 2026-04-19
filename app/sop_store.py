from __future__ import annotations

from app.schemas import GeneratedSOP

_STORE: dict[str, GeneratedSOP] = {}


def get_sop(sop_id: str) -> GeneratedSOP | None:
    return _STORE.get(sop_id)


def save_or_reuse(sop: GeneratedSOP) -> tuple[GeneratedSOP, bool]:
    sid = sop.sop_id
    existing = _STORE.get(sid)
    if existing is not None:
        return existing, True
    _STORE[sid] = sop
    return sop, False


def search_sops(service: str | None, root_cause: str | None) -> list[GeneratedSOP]:
    rows = list(_STORE.values())
    if service and service.strip():
        q = service.strip().lower()
        rows = [
            x
            for x in rows
            if any(q in v.lower() for v in x.services_involved)
        ]
    if root_cause and root_cause.strip():
        q = root_cause.strip().lower()
        rows = [x for x in rows if q in x.root_cause.lower()]
    return rows


def clear_store() -> None:
    _STORE.clear()
