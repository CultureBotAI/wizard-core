"""Thin Anthropic SDK wrapper with prompt caching and message helpers.

Centralizes Anthropic API access for all wizard tools so that:
- Model defaults are consistent (Claude Opus 4.7 as default).
- Prompt caching is enabled with sensible breakpoints.
- Tools don't each reinvent retry/streaming/system-prompt scaffolding.

This is intentionally minimal. Tools should call `LLMClient.complete()` for
one-shot generations and `LLMClient.complete_with_cache()` when reusing a
large system prompt or context across many calls.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

try:
    import anthropic
except ImportError:  # pragma: no cover - allow import without SDK installed
    anthropic = None  # type: ignore


DEFAULT_MODEL = "claude-opus-4-7"
DEFAULT_MAX_TOKENS = 4096


@dataclass
class LLMResponse:
    text: str
    stop_reason: Optional[str]
    usage: Dict[str, int] = field(default_factory=dict)
    raw: Any = None


class LLMClient:
    """Anthropic Messages-API client with prompt-cache helpers."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        default_max_tokens: int = DEFAULT_MAX_TOKENS,
    ):
        if anthropic is None:
            raise ImportError(
                "anthropic SDK not installed. Add `anthropic` to your dependencies."
            )
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. Export it or pass api_key=..."
            )
        self.model = model
        self.default_max_tokens = default_max_tokens
        self.logger = logging.getLogger(__name__)
        self._client = anthropic.Anthropic(api_key=self.api_key)

    def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Single-turn user prompt completion."""
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens or self.default_max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        resp = self._client.messages.create(**kwargs)
        return self._unpack(resp)

    def complete_with_cache(
        self,
        prompt: str,
        cached_system: str,
        cached_context: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Completion with cacheable system prompt and optional cacheable context.

        Use this when calling the model many times against the same large
        reference document (e.g., draft each slide against the same source
        analysis). The cached content gets a `cache_control` breakpoint so
        subsequent calls within the cache TTL pay only for the new tokens.
        """
        system_blocks: List[Dict[str, Any]] = [
            {
                "type": "text",
                "text": cached_system,
                "cache_control": {"type": "ephemeral"},
            }
        ]
        user_content: List[Dict[str, Any]] = []
        if cached_context:
            user_content.append(
                {
                    "type": "text",
                    "text": cached_context,
                    "cache_control": {"type": "ephemeral"},
                }
            )
        user_content.append({"type": "text", "text": prompt})

        resp = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens or self.default_max_tokens,
            temperature=temperature,
            system=system_blocks,
            messages=[{"role": "user", "content": user_content}],
        )
        return self._unpack(resp)

    @staticmethod
    def _unpack(resp: Any) -> LLMResponse:
        text_parts: List[str] = []
        for block in getattr(resp, "content", []) or []:
            if getattr(block, "type", None) == "text":
                text_parts.append(block.text)
        usage_obj = getattr(resp, "usage", None)
        usage = {}
        if usage_obj is not None:
            for k in (
                "input_tokens",
                "output_tokens",
                "cache_creation_input_tokens",
                "cache_read_input_tokens",
            ):
                v = getattr(usage_obj, k, None)
                if v is not None:
                    usage[k] = v
        return LLMResponse(
            text="".join(text_parts),
            stop_reason=getattr(resp, "stop_reason", None),
            usage=usage,
            raw=resp,
        )
