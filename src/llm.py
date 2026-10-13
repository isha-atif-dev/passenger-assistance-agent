"""LLM access with Gemini as the primary provider and Groq as a fallback."""

import json
import logging

import requests

from src import config

logger = logging.getLogger(__name__)

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def _call_gemini(prompt: str) -> str:
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
    }
    response = requests.post(
        GEMINI_URL,
        headers={"x-goog-api-key": config.GEMINI_API_KEY},
        json=body,
        timeout=config.LLM_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()["candidates"][0]["content"]["parts"][0]["text"]


def _call_groq(prompt: str) -> str:
    body = {
        "model": config.GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }
    response = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
        json=body,
        timeout=config.LLM_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def ask_json(prompt: str) -> dict:
    """Send a prompt and return the parsed JSON reply, trying each provider in turn."""
    for name, call in (("gemini", _call_gemini), ("groq", _call_groq)):
        try:
            return json.loads(call(prompt))
        except (requests.RequestException, KeyError, ValueError) as error:
            logger.warning("%s failed: %s", name, error)
    raise RuntimeError("All LLM providers failed")