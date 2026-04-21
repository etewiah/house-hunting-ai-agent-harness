from __future__ import annotations

import anthropic

from src.models.prompts import SYSTEM_BOUNDARY


class AnthropicAdapter:
    """LlmAdapter implementation backed by the Anthropic API with prompt caching."""

    def __init__(self) -> None:
        self.client = anthropic.Anthropic()

    def generate(self, prompt: str, model: str) -> str:
        response = self.client.messages.create(
            model=model,
            max_tokens=1024,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_BOUNDARY,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
