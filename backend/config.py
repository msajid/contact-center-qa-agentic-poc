"""Runtime configuration for the Contact Center QA POC.

Values are read from environment variables (optionally via a local ``.env``
file). The application is designed to run with or without a Microsoft Foundry
project configured:

* When ``FOUNDRY_PROJECT_ENDPOINT`` is set, the agents run for real through the
  Microsoft Agent Framework Foundry chat client.
* When it is not set (or a live call fails), the agents fall back to a rich,
  deterministic simulation so the POC is always demonstrable.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from dotenv import load_dotenv

from .observability import setup_logging

# Agent Framework does not auto-load .env files, so we do it here explicitly.
load_dotenv()

# Configure console tracing as early as possible (before any other module logs).
setup_logging()

logger = logging.getLogger("ccqa.config")


@dataclass(frozen=True)
class Settings:
    """Strongly typed view over the POC's environment configuration."""

    foundry_project_endpoint: str = os.getenv("FOUNDRY_PROJECT_ENDPOINT", "").strip()
    foundry_model: str = os.getenv("FOUNDRY_MODEL", "gpt-4o").strip() or "gpt-4o"
    credential_type: str = os.getenv("AZURE_CREDENTIAL", "default").strip().lower()
    enable_web_search: bool = os.getenv("ENABLE_WEB_SEARCH", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    @property
    def foundry_configured(self) -> bool:
        """True when enough configuration exists to attempt a live agent run."""
        return bool(self.foundry_project_endpoint)


settings = Settings()

logger.debug(
    "Settings resolved: mode=%s foundry_configured=%s endpoint=%s model=%s credential=%s web_search=%s",
    "live" if settings.foundry_configured else "simulation",
    settings.foundry_configured,
    settings.foundry_project_endpoint or "(unset)",
    settings.foundry_model,
    settings.credential_type,
    settings.enable_web_search,
)
