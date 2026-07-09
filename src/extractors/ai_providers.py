"""Provider-agnostic LLM client.

The AI extraction path must not be locked to one vendor - this module is
the single seam where OpenAI / Anthropic / Gemini differences are absorbed,
so `ai_extractor.py` only ever calls `.complete_json(prompt, schema)` and
never touches an SDK directly.

Add a new provider by subclassing `LLMProvider` and registering it in
`get_provider()` - nothing else in the codebase needs to change.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any


class ProviderError(RuntimeError):
    """Raised when a provider call fails or returns unparseable output."""


class LLMProvider(ABC):
    """A chat-completion backend that can be asked to return structured JSON."""

    @abstractmethod
    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        """Send a prompt, return the parsed JSON object from the response.

        Implementations are responsible for instructing their model to
        return JSON-only output and for stripping any markdown code-fence
        wrapping before parsing.
        """
        raise NotImplementedError


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.replace("```json", "").replace("```", "")
    return text.strip()


class OpenAIProvider(LLMProvider):
    def __init__(self, model: str | None = None) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ProviderError("OPENAI_API_KEY is not set.")
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
            )
            content = response.choices[0].message.content or "{}"
            return json.loads(_strip_code_fence(content))
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"OpenAI request failed: {exc}") from exc


class AnthropicProvider(LLMProvider):
    def __init__(self, model: str | None = None) -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ProviderError("ANTHROPIC_API_KEY is not set.")
        import anthropic

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            content = "".join(
                block.text for block in response.content if getattr(block, "type", None) == "text"
            )
            return json.loads(_strip_code_fence(content))
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Anthropic request failed: {exc}") from exc


class GeminiProvider(LLMProvider):
    def __init__(self, model: str | None = None) -> None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ProviderError("GEMINI_API_KEY is not set.")
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        self.model_name = model or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        self.model = genai.GenerativeModel(self.model_name)

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        try:
            response = self.model.generate_content(
                f"{system_prompt}\n\n{user_prompt}",
                generation_config={"temperature": 0, "response_mime_type": "application/json"},
            )
            return json.loads(_strip_code_fence(response.text))
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Gemini request failed: {exc}") from exc


_PROVIDERS = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
}


def get_provider(name: str | None = None) -> LLMProvider:
    """Instantiate the configured provider.

    `name` overrides the `AI_PROVIDER` env var (which itself defaults to
    'anthropic'). Raises ProviderError with an actionable message if the
    requested provider's SDK isn't installed or its API key is missing.
    """
    provider_name = (name or os.getenv("AI_PROVIDER", "anthropic")).lower()
    provider_cls = _PROVIDERS.get(provider_name)
    if provider_cls is None:
        raise ProviderError(
            f"Unknown AI_PROVIDER '{provider_name}'. Choose one of: {list(_PROVIDERS)}"
        )
    return provider_cls()
