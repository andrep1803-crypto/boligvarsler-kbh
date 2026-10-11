"""Tynd klient til Telegram Bot API (kun udgående beskeder)."""

from __future__ import annotations

import logging

import httpx

log = logging.getLogger("boligagent.telegram")

API = "https://api.telegram.org"


class Telegram:
    def __init__(self, token: str, chat_id: str, timeout: float = 30.0):
        self.token = token
        self.chat_id = chat_id
        self.timeout = timeout
        self.enabled = bool(token and chat_id)

    def _post(self, method: str, payload: dict) -> bool:
        if not self.enabled:
            log.warning("Telegram ikke konfigureret – springer '%s' over.", method)
            return False
        url = f"{API}/bot{self.token}/{method}"
        try:
            resp = httpx.post(url, data=payload, timeout=self.timeout)
            if resp.status_code != 200:
                log.error("Telegram %s fejlede: %s %s", method, resp.status_code, resp.text[:300])
                return False
            return True
        except httpx.HTTPError as exc:
            log.error("Telegram %s netværksfejl: %s", method, exc)
            return False

    def send_message(self, text: str, disable_preview: bool = False) -> bool:
        return self._post(
            "sendMessage",
            {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": disable_preview,
            },
        )

    def send_photo(self, photo_url: str, caption: str) -> bool:
        """Sender billede med tekst. Falder tilbage til ren besked ved fejl."""
        ok = self._post(
            "sendPhoto",
            {
                "chat_id": self.chat_id,
                "photo": photo_url,
                "caption": caption,
                "parse_mode": "HTML",
            },
        )
        if not ok:
            # Billedet kunne være for stort / utilgængeligt – send i det mindste teksten.
            return self.send_message(caption)
        return True
