"""CDC – ledige lejligheder.

⚠️ DOMÆNE IKKE BEKRÆFTET
    "CDC" kunne ikke verificeres entydigt i Fase 1 (søgninger pegede bl.a.
    fejlagtigt på EDC). Før scraperen kan bruges skal den rigtige side findes
    og felterne kortlægges – på samme måde som de øvrige scrapere.

    Når du kender siden:
      1) Afgør datakilde (inline HTML / JSON-API / JavaScript-renderet).
      2) Hvis simpel HTML: lad klassen arve fra GenericHtmlScraper og sæt
         LIST_URL, BASE_URL og CARD_SELECTOR.
      3) Hvis API: skriv fetch() som i boligsiden.py.

Status: IKKE aktiv. Returnerer en tom liste (fejler ikke). Slå evt. 'cdc' fra
i config.yaml indtil domænet er bekræftet.
"""

from __future__ import annotations

import logging

from boligagent.models import Listing
from .base import BaseScraper

log = logging.getLogger("boligagent.scraper.cdc")


class CdcScraper(BaseScraper):
    name = "cdc"
    source = "CDC"

    def fetch(self) -> list[Listing]:
        log.info("[cdc] domæne ikke bekræftet endnu – scraper er en stub. Returnerer 0.")
        return []
