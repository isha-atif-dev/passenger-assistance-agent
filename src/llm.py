"""LLM access with Gemini as the primary provider and Groq as a fallback."""

import json
import logging
import time

import requests
from langfuse import get_client, observe

from src import config

logger = logging.getLogger(__name__)

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
RATE_LIMIT_WAIT_SECONDS = 5


def _post(url: str, headers: dict, body: dict) -> dict:
    """POST with one retry on rate limiting. Errors include the provider's message."""
    response = requests.post(url, headers=headers, json=body, timeout=config.LLM_TIMEOUT)
    if response.status_code == 429:
        # A short wait usually clears free-tier rate limits
        time.sleep(RATE_LIMIT_WAIT_SECONDS)
        response = requests.post(url, headers=headers, json=body, timeout=config.LLM_TIMEOUT)
    if not response.ok:
        raise requests.HTTPError(f"{response.status_code} {response.text[:200]}", response=response)
    return response.json()


@observe(as_type="generation", name="gemini")
def _call_gemini(prompt: str) -> str:
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
    }
    data = _post(GEMINI_URL, {"x-goog-api-key": config.GEMINI_API_KEY}, body)

    usage = data.get("usageMetadata", {})
    get_client().update_current_generation(
        model=config.GEMINI_MODEL,
        usage_details={
            "input": usage.get("promptTokenCount", 0),
            "output": usage.get("candidatesTokenCount", 0),
        },
    )
    return data["candidates"][0]["content"]["parts"][0]["text"]


@observe(as_type="generation", name="groq")
def _call_groq(prompt: str) -> str:
    body = {
        "model": config.GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }
    data = _post(GROQ_URL, {"Authorization": f"Bearer {config.GROQ_API_KEY}"}, body)

    usage = data.get("usage", {})
    get_client().update_current_generation(
        model=config.GROQ_MODEL,
        usage_details={
            "input": usage.get("prompt_tokens", 0),
            "output": usage.get("completion_tokens", 0),
        },
    )
    return data["choices"][0]["message"]["content"]


def ask_json(prompt: str) -> dict:
    """Send a prompt and return the parsed JSON reply, trying each provider in turn."""
    for name, call in (("gemini", _call_gemini), ("groq", _call_groq)):
        try:
            return json.loads(call(prompt))
        except (requests.RequestException, KeyError, ValueError) as error:
            logger.warning("%s failed: %s", name, error)
    raise RuntimeError("All LLM providers failed")