"""Source-neutral input contracts; never infer permissions from age or keywords."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

RIGHTS = frozenset({"public_domain", "cc0", "restricted", "unknown"})
DECISIONS = frozenset({"include", "skip", "review"})


class ContractError(ValueError):
    """Input failed its normalized interface."""


def _required_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{name} must be nonempty text")
    return value.strip()


def validate_artwork(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise ContractError("artwork must be a mapping")
    result = {
        field: _required_text(record.get(field), field)
        for field in ("source_id", "object_id", "title", "rights_status")
    }
    if result["rights_status"] not in RIGHTS:
        raise ContractError("unsupported rights_status")
    for field in ("artist", "source_category", "source_url", "image_url"):
        value = record.get(field)
        if value is not None:
            if not isinstance(value, str):
                raise ContractError(f"{field} must be text or null")
            result[field] = value.strip()
    return result


def eligible_for_download(record: Mapping[str, Any], *, source_approved: bool) -> bool:
    """Fail closed: approved source + explicit PD/CC0 + HTTPS image required."""
    if source_approved is not True:
        return False
    try:
        artwork = validate_artwork(record)
    except ContractError:
        return False
    if artwork["rights_status"] not in {"public_domain", "cc0"}:
        return False
    parsed = urlparse(artwork.get("image_url", ""))
    return parsed.scheme == "https" and bool(parsed.netloc)


def validate_curator_decision(
    payload: Mapping[str, Any], *, candidate_keys: set[str]
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ContractError("decision must be a mapping")
    if set(payload) != {"candidate_key", "decision", "score", "reason"}:
        raise ContractError("decision fields mismatch")
    key = _required_text(payload["candidate_key"], "candidate_key")
    if key not in candidate_keys:
        raise ContractError("candidate not found in this batch")
    decision = _required_text(payload["decision"], "decision")
    if decision not in DECISIONS:
        raise ContractError("unsupported decision")
    score = payload["score"]
    if type(score) is not int or not 0 <= score <= 100:
        raise ContractError("score must be an integer in [0, 100]")
    reason = _required_text(payload["reason"], "reason")
    return {"candidate_key": key, "decision": decision, "score": score, "reason": reason}
