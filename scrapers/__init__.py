"""Scrapere – én modul pr. nettside, alle med samme grænseflade.

Hver scraper er en subklasse af BaseScraper og implementerer fetch() der
returnerer en liste af Listing-objekter. Registreres i REGISTRY nedenfor.
"""

from __future__ import annotations

from .base import BaseScraper, ScrapeContext
from .heimstaden import HeimstadenScraper
from .cej import CejScraper
from .cdc import CdcScraper
from .cityapartment import CityApartmentScraper
from .boligsiden import BoligsidenScraper
from .findbolig import FindboligScraper
from .boligportal import BoligPortalScraper
from .lejebolig import LejeboligScraper

# Nøgle skal matche navnene under "kilder:" i config.yaml.
REGISTRY: dict[str, type[BaseScraper]] = {
    "heimstaden": HeimstadenScraper,
    "cej": CejScraper,
    "cdc": CdcScraper,
    "cityapartment": CityApartmentScraper,
    "boligsiden": BoligsidenScraper,
    "findbolig": FindboligScraper,
    "boligportal": BoligPortalScraper,
    "lejebolig": LejeboligScraper,
}

__all__ = ["BaseScraper", "ScrapeContext", "REGISTRY"]
