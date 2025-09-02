"""Define the configurable parameters for the agent."""

from __future__ import annotations

import os
from datetime import date
from dataclasses import dataclass, field, fields
from typing import Annotated

from langchain_core.runnables import ensure_config
from langgraph.config import get_config

from react_agent import prompts


@dataclass(kw_only=True)
class Configuration:
    """The configuration for the agent."""

    system_prompt: str = field(
        default=prompts.SYSTEM_PROMPT,
        metadata={
            "description": "The system prompt to use for the agent's interactions. "
            "This prompt sets the context and behavior for the agent."
        },
    )

    model: Annotated[str, {"__template_metadata__": {"kind": "llm"}}] = field(
        default="ollama/gpt-OSS:20b",
        metadata={
            "description": "The name of the language model to use for the agent's main interactions. "
            "Should be in the form: provider/model-name."
        }
    )

    django_api_base_url: str = field(
        default_factory=lambda: os.getenv("DJANGO_API_BASE_URL", "http://localhost:8000/api"),
        metadata={
            "description": "Base URL for the Django API endpoints (from DJANGO_API_BASE_URL env var)"
        },
    )

    django_api_token: str = field(
        default_factory=lambda: os.getenv("DJANGO_API_TOKEN", ""),
        metadata={
            "description": "Authentication token for Django API access (from DJANGO_API_TOKEN env var)"
        },
    )

    max_search_results: int = field(
        default=10,
        metadata={
            "description": "The maximum number of search results to return for each search query."
        },
    )

    @classmethod
    def from_context(cls) -> Configuration:
        """Create a Configuration instance from a RunnableConfig object."""
        try:
            config = get_config()
        except RuntimeError:
            config = None
        config = ensure_config(config)
        configurable = config.get("configurable") or {}
        _fields = {f.name for f in fields(cls) if f.init}
        return cls(**{k: v for k, v in configurable.items() if k in _fields})
