from __future__ import annotations

import os

from src.models.prompts import SYSTEM_BOUNDARY


class OpenAIAdapter:
    """LlmAdapter for OpenAI and any OpenAI-compatible API.

    Covers: OpenAI, Ollama (local), Groq, Together, LM Studio, Mistral, etc.
    All use the same client; point OPENAI_BASE_URL at the provider's endpoint.
    """

    def __init__(self) -> None:
        try:
            import openai
        except ImportError:
            raise ImportError(
                "openai package not installed. Run: uv add openai"
            )
        self.client = openai.OpenAI(
            api_key=os.getenv("OPENAI_API_KEY", "not-needed"),
            base_url=os.getenv("OPENAI_BASE_URL") or None,
        )
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def generate(self, prompt: str, model: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=1024,
            messages=[
                {"role": "system", "content": SYSTEM_BOUNDARY},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content
