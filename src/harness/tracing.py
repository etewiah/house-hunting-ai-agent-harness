from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Literal

TraceEventName = Literal[
    "intake.profile_created",
    "triage.ranked_listings",
    "triage.explanations",
    "comparison.summary",
    "comparison.created",
    "next_steps.prepared",
]


class TraceRecorder:
    def __init__(self, output_dir: str) -> None:
        self.output_dir = Path(output_dir)
        self.events: list[dict[str, object]] = []

    def record(self, name: TraceEventName, payload: object) -> None:
        self.events.append(
            {
                "at": datetime.now(timezone.utc).isoformat(),
                "name": name,
                "payload": _to_jsonable(payload),
            }
        )

    def flush(self, session_id: str = "demo") -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"{session_id}.json"
        path.write_text(json.dumps(self.events, indent=2), encoding="utf-8")
        return path


def _to_jsonable(value: object) -> object:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    return value
