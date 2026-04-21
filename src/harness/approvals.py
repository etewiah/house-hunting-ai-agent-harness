from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ApprovalRequest:
    action: str
    reason: str
    required: bool = True


def require_human_approval(action: str, reason: str) -> ApprovalRequest:
    return ApprovalRequest(action=action, reason=reason)
