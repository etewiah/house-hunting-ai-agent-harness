from __future__ import annotations


def estimate_commute_minutes(origin: str, destination: str) -> int | None:
    if not origin or not destination:
        return None
    return 45
