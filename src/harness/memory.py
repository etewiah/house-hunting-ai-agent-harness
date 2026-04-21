from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Memory:
    facts: dict[str, object] = field(default_factory=dict)

    def remember(self, key: str, value: object) -> None:
        self.facts[key] = value

    def recall(self, key: str, default: object = None) -> object:
        return self.facts.get(key, default)
