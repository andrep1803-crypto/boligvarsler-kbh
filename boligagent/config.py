"""Indlæser config.yaml og hemmeligheder fra miljøet/.env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

try:
    from dotenv import load_dotenv
except ImportError:  # dotenv er valgfri i produktion (GitHub Actions bruger Secrets)
    def load_dotenv(*_args, **_kwargs):  # type: ignore
        return False


ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"


@dataclass
class Secrets:
    telegram_bot_token: str
    telegram_chat_id: str
    kontakt_navn: str
    kontakt_tlf: str
    kontakt_adresse: str

    @property
    def telegram_ready(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_secrets() -> Secrets:
    """Henter hemmeligheder. Lokalt fra .env, i skyen fra miljøvariabler."""
    load_dotenv(ROOT / ".env")
    return Secrets(
        telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID", ""),
        kontakt_navn=os.environ.get("KONTAKT_NAVN", ""),
        kontakt_tlf=os.environ.get("KONTAKT_TLF", ""),
        kontakt_adresse=os.environ.get("KONTAKT_ADRESSE", ""),
    )
