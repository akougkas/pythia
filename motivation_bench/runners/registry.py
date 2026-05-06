"""Model registry. Edit this file to add or remove models.

Local model URLs default to standard endpoints; override via env if needed:
    OLLAMA_BASE_URL  (default: http://localhost:11434/v1)
    VLLM_BASE_URL    (default: http://localhost:8000/v1)
"""

from __future__ import annotations

import os

from .models import ModelSpec

# ── Anthropic models (cloud) ──────────────────────────────────────────

ANTHROPIC_MODELS: list[ModelSpec] = [
    ModelSpec(name="claude-haiku-4-5",   provider="anthropic", label="Haiku 4.5"),
    ModelSpec(name="claude-sonnet-4-6",  provider="anthropic", label="Sonnet 4.6"),
    ModelSpec(name="claude-opus-4-6",    provider="anthropic", label="Opus 4.6"),
    ModelSpec(name="claude-opus-4-7",    provider="anthropic", label="Opus 4.7"),
]

# ── Local models (Ollama / vLLM / LM Studio) ──────────────────────────

OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
VLLM_BASE = os.environ.get("VLLM_BASE_URL", "http://localhost:8000/v1")

LOCAL_MODELS: list[ModelSpec] = [
    ModelSpec(
        name="gpt-oss:20b",
        provider="ollama",
        api_base_url=OLLAMA_BASE,
        label="gpt-oss-20b (Ollama)",
        # Ollama's /v1/messages emits thinking blocks without signatures,
        # which the Claude Code CLI rejects. Disable thinking for this model.
        disable_thinking=True,
    ),
    ModelSpec(
        name="gemma4:26b",
        provider="ollama",
        api_base_url=OLLAMA_BASE,
        label="gemma4-26b (Ollama)",
        # Ollama's /v1/messages emits thinking blocks without signatures,
        # which the Claude Code CLI rejects. Disable thinking for this model.
        disable_thinking=True,
    ),
    ModelSpec(
        name="mistral-small3.2:24b",
        provider="ollama",
        api_base_url=OLLAMA_BASE,
        label="mistral-small3.2-24b (Ollama)",
        # Ollama's /v1/messages emits thinking blocks without signatures,
        # which the Claude Code CLI rejects. Disable thinking for this model.
        disable_thinking=True,
    ),
    ModelSpec(
        name="qwen3.5:9b",
        provider="ollama",
        api_base_url=OLLAMA_BASE,
        label="qwen3.5-9b (Ollama)",
        # Ollama's /v1/messages emits thinking blocks without signatures,
        # which the Claude Code CLI rejects. Disable thinking for this model.
        disable_thinking=True,
    ),
    # Add more local models here. Example:
    # ModelSpec(name="qwen2.5-coder:14b", provider="ollama",
    #           api_base_url=OLLAMA_BASE, label="qwen2.5-coder-14b"),
]

ALL_MODELS: list[ModelSpec] = ANTHROPIC_MODELS + LOCAL_MODELS


def get_model(name: str) -> ModelSpec:
    for m in ALL_MODELS:
        if m.name == name:
            return m
    raise KeyError(
        f"Unknown model: {name!r}. Add it to runners/registry.py "
        f"or pick from: {[m.name for m in ALL_MODELS]}"
    )
