import os

import httpx


class LLMError(RuntimeError):
    """The LLM could not be reached or gave no usable response."""


def call_llm(messages: list[dict]) -> str:
    """Call any OpenAI-compatible chat completions endpoint."""
    base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    api_key = os.environ.get("LLM_API_KEY")
    model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    timeout = float(os.environ.get("LLM_TIMEOUT", "30"))

    if not api_key:
        raise LLMError("LLM_API_KEY is not set")

    try:
        response = httpx.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": messages,
                "temperature": 0,
                "max_tokens": 600,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise LLMError("LLM request failed") from exc
