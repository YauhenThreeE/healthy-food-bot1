from __future__ import annotations

import os
from dataclasses import dataclass

from openai import AsyncOpenAI


@dataclass(frozen=True)
class AIProviderConfig:
    provider: str
    model: str
    client: AsyncOpenAI


def get_ai_provider() -> AIProviderConfig | None:
    groq_key = (os.getenv("GROQ_API_KEY") or "").strip()
    if groq_key:
        base = (os.getenv("GROQ_BASE_URL") or "https://api.groq.com/openai/v1").strip()
        model = (os.getenv("GROQ_MODEL") or "llama-3.3-70b-versatile").strip()
        return AIProviderConfig(
            provider="groq",
            model=model,
            client=AsyncOpenAI(api_key=groq_key, base_url=base, timeout=90.0, max_retries=1),
        )

    openai_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if openai_key:
        model = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
        return AIProviderConfig(
            provider="openai",
            model=model,
            client=AsyncOpenAI(api_key=openai_key, timeout=90.0, max_retries=1),
        )
    return None
