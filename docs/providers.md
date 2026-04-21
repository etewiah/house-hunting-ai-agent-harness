# LLM Provider Configuration

The harness works with any LLM that implements the `LlmAdapter` protocol
(`generate(prompt, model) -> str`). Provider selection is automatic based on
environment variables, or can be forced with `LLM_PROVIDER`.

## Quick reference

| Provider | `LLM_PROVIDER` | Key env var | Cost |
|---|---|---|---|
| Anthropic (Claude) | `anthropic` | `ANTHROPIC_API_KEY` | Paid |
| OpenAI | `openai` | `OPENAI_API_KEY` | Paid |
| Ollama (local) | `ollama` | none needed | Free |
| Groq | `groq` | `OPENAI_API_KEY` | Free tier |
| Together AI | `together` | `OPENAI_API_KEY` | Paid |
| LM Studio (local) | `lm_studio` | none needed | Free |

## Auto-detection

If `LLM_PROVIDER` is not set, the harness picks a provider automatically:

1. `ANTHROPIC_API_KEY` is set → Anthropic (Claude)
2. `OPENAI_API_KEY` or `OPENAI_BASE_URL` is set → OpenAI-compatible
3. Neither → demo mode (regex parsing, no AI)

## Anthropic (Claude) — recommended

```bash
export ANTHROPIC_API_KEY=sk-ant-...
uv run house-hunt
```

Uses `claude-haiku-4-5-20251001` by default for intake and explanations
(fast, cheap, accurate). Override per-operation with:

```bash
export BUYER_AGENT_INTAKE_MODEL=claude-sonnet-4-6
export BUYER_AGENT_EXPLAIN_MODEL=claude-sonnet-4-6
```

## OpenAI

```bash
export OPENAI_API_KEY=sk-...
export OPENAI_MODEL=gpt-4o-mini   # default
uv run house-hunt
```

## Ollama (local, free)

Run any model locally with no API key. Requires [Ollama](https://ollama.com) installed.

```bash
ollama pull llama3.2
export LLM_PROVIDER=ollama
export OPENAI_BASE_URL=http://localhost:11434/v1
export OPENAI_MODEL=llama3.2
uv run house-hunt
```

`OPENAI_API_KEY` is not required for Ollama.

## Groq (fast inference, free tier)

```bash
export LLM_PROVIDER=groq
export OPENAI_API_KEY=gsk_...      # Groq API key
export OPENAI_BASE_URL=https://api.groq.com/openai/v1
export OPENAI_MODEL=llama-3.1-70b-versatile
uv run house-hunt
```

## Together AI

```bash
export LLM_PROVIDER=together
export OPENAI_API_KEY=...
export OPENAI_BASE_URL=https://api.together.xyz/v1
export OPENAI_MODEL=meta-llama/Llama-3.2-90B-Vision-Instruct-Turbo
uv run house-hunt
```

## LM Studio (local)

Start LM Studio's local server (default port 1234), then:

```bash
export LLM_PROVIDER=lm_studio
export OPENAI_BASE_URL=http://localhost:1234/v1
export OPENAI_MODEL=your-loaded-model
uv run house-hunt
```

## Adding a new provider

Implement the `LlmAdapter` protocol from `src/skills/intake.py`:

```python
class LlmAdapter(Protocol):
    def generate(self, prompt: str, model: str) -> str: ...
```

See `src/connectors/anthropic_adapter.py` and `src/connectors/openai_adapter.py`
as reference implementations. Then register it in `src/connectors/provider_factory.py`.

## MCP server

The MCP server (`uv run house-hunt serve`) uses the same provider detection.
Set the same environment variables before starting the server.
