"""Provider selection.

One place to switch the whole demo between an offline scripted model (no keys, no
network) and a real model behind Azure OpenAI, Microsoft Foundry, OpenAI, Anthropic or
Ollama. Every agent in the demo gets its chat client from ``make_client``.
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()

PROVIDERS = ("offline", "azure", "foundry", "openai", "anthropic", "ollama")


def detect_provider() -> str:
    """Return the provider name, from AGENT_PROVIDER or by sniffing environment variables."""
    explicit = os.getenv("AGENT_PROVIDER", "").strip().lower()
    if explicit:
        if explicit not in PROVIDERS:
            raise ValueError(f"AGENT_PROVIDER must be one of {PROVIDERS}, got {explicit!r}")
        return explicit
    if os.getenv("FOUNDRY_PROJECT_ENDPOINT"):
        return "foundry"
    if os.getenv("AZURE_OPENAI_ENDPOINT"):
        return "azure"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("OLLAMA_HOST") or os.getenv("OLLAMA_CHAT_MODEL"):
        return "ollama"
    return "offline"


def is_live() -> bool:
    """True when a real model provider is configured."""
    return detect_provider() != "offline"


def describe_provider() -> str:
    """Human readable one-liner for banners."""
    provider = detect_provider()
    if provider == "offline":
        return "offline scripted model (no API keys needed)"
    if provider == "azure":
        return f"Azure OpenAI ({os.getenv('AZURE_OPENAI_CHAT_MODEL', 'default model')})"
    if provider == "foundry":
        return f"Microsoft Foundry ({os.getenv('FOUNDRY_MODEL', 'default model')})"
    if provider == "openai":
        return f"OpenAI ({os.getenv('OPENAI_CHAT_MODEL', 'default model')})"
    if provider == "anthropic":
        return f"Anthropic ({os.getenv('ANTHROPIC_CHAT_MODEL', 'default model')})"
    return f"Ollama ({os.getenv('OLLAMA_CHAT_MODEL', 'default model')})"


def make_client(role: str = "assistant") -> Any:
    """Create a chat client for an agent.

    ``role`` only matters for the offline provider, where it selects the scripted persona.
    Real providers ignore it.
    """
    provider = detect_provider()

    if provider == "offline":
        from .offline_client import OfflineChatClient

        return OfflineChatClient(role=role)

    if provider == "azure":
        from agent_framework.openai import OpenAIChatClient

        kwargs: dict[str, Any] = {
            "azure_endpoint": os.environ["AZURE_OPENAI_ENDPOINT"],
            "model": os.getenv("AZURE_OPENAI_CHAT_MODEL"),
        }
        if os.getenv("AZURE_OPENAI_API_VERSION"):
            kwargs["api_version"] = os.environ["AZURE_OPENAI_API_VERSION"]
        if os.getenv("AZURE_OPENAI_API_KEY"):
            kwargs["api_key"] = os.environ["AZURE_OPENAI_API_KEY"]
        else:
            from azure.identity import AzureCliCredential

            kwargs["credential"] = AzureCliCredential()
        return OpenAIChatClient(**kwargs)

    if provider == "foundry":
        from agent_framework.foundry import FoundryChatClient
        from azure.identity import AzureCliCredential

        return FoundryChatClient(
            project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
            model=os.getenv("FOUNDRY_MODEL"),
            credential=AzureCliCredential(),
        )

    if provider == "openai":
        from agent_framework.openai import OpenAIChatClient

        return OpenAIChatClient()

    if provider == "anthropic":
        from agent_framework.anthropic import AnthropicClient

        return AnthropicClient()

    if provider == "ollama":
        from agent_framework.ollama import OllamaChatClient

        return OllamaChatClient()

    raise ValueError(f"Unknown provider {provider!r}")
