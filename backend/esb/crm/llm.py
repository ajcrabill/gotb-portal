"""CRM LLM helper — OpenRouter JSON completion, shared by verifier/dossier/
newsworthy/governance-writer/presentation/lead-gen. Ported from coach-devon's
services/llm.py, adapted to async httpx matching the portal's eval/analyzer.py
pattern.
"""
from __future__ import annotations

import json

import httpx

from esb.core.config import settings


class LLMUnavailable(RuntimeError):
    pass


def configured() -> bool:
    return bool(settings.openrouter_api_key)


async def complete_json(system: str, user: str, max_tokens: int = 1500, temperature: float = 0.2) -> dict:
    if not settings.openrouter_api_key:
        raise LLMUnavailable("OPENROUTER_API_KEY not set")

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "X-Title": "ESB Portal CRM",
    }
    payload = {
        "model": "deepseek/deepseek-v4-flash",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    last_err = None
    url = f"{settings.openrouter_base_url}/chat/completions"
    async with httpx.AsyncClient(timeout=60) as client:
        for _ in range(2):
            try:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                return json.loads(resp.json()["choices"][0]["message"]["content"])
            except (json.JSONDecodeError, KeyError) as e:
                last_err = e
                continue
    raise ValueError(f"LLM returned unparseable JSON: {last_err}")


def complete_json_sync(system: str, user: str, max_tokens: int = 1500, temperature: float = 0.2) -> dict:
    """Sync variant for use inside thread-pooled sync pipelines (verifier), where
    nesting an event loop would be awkward. Same semantics as complete_json."""
    if not settings.openrouter_api_key:
        raise LLMUnavailable("OPENROUTER_API_KEY not set")

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "X-Title": "ESB Portal CRM",
    }
    payload = {
        "model": "deepseek/deepseek-v4-flash",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    url = f"{settings.openrouter_base_url}/chat/completions"
    last_err = None
    with httpx.Client(timeout=60) as client:
        for _ in range(2):
            try:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                return json.loads(resp.json()["choices"][0]["message"]["content"])
            except (json.JSONDecodeError, KeyError) as e:
                last_err = e
                continue
    raise ValueError(f"LLM returned unparseable JSON: {last_err}")
