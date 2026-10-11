"""Base-klasse og fælles kontekst for alle scrapere."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from boligagent.models import Listing

log = logging.getLogger("boligagent.scraper")


@dataclass
class ScrapeContext:
    """Delte indstillinger (fra config.yaml -> hentning:)."""

    user_agent: str
    delay_seconds: float = 2.0
    timeout_seconds: float = 30.0


class BaseScraper:
    """Fælles grænseflade. Subklasser sætter ``name``/``source`` og
    implementerer :meth:`fetch`.
    """

    name: str = "base"       # nøgle i config/registry
    source: str = "Base"     # pænt navn der vises i varsler

    def __init__(self, ctx: ScrapeContext):
        self.ctx = ctx
        self._client = httpx.Client(
            headers={
                "User-Agent": ctx.user_agent,
                "Accept-Language": "da-DK,da;q=0.9,en;q=0.8",
            },
            timeout=ctx.timeout_seconds,
            follow_redirects=True,
        )
        self._last_request = 0.0

    # --- hentnings-hjælpere med skånsom forsinkelse -----------------------

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request
        wait = self.ctx.delay_seconds - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        self._throttle()
        log.debug("[%s] GET %s", self.name, url)
        resp = self._client.get(url, **kwargs)
        resp.raise_for_status()
        return resp

    def get_json(self, url: str, **kwargs: Any) -> Any:
        headers = kwargs.pop("headers", {})
        headers.setdefault("Accept", "application/json")
        return self.get(url, headers=headers, **kwargs).json()

    def close(self) -> None:
        self._client.close()

    # --- skal implementeres af subklasser ---------------------------------

    def fetch(self) -> list[Listing]:
        raise NotImplementedError

    def __enter__(self) -> "BaseScraper":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
