from __future__ import annotations


def draft_notification(channel: str, message: str) -> dict[str, object]:
    return {
        "channel": channel,
        "message": message,
        "requires_approval": True,
    }
