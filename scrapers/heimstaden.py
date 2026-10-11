"""Heimstaden – https://www.heimstaden.dk/ledige-lejeboliger/

Datakilde (VERIFICERET live): Siden er WordPress og viser ALLE ~248 ledige
boliger direkte i HTML'en på oversigtssiden (ingen __NEXT_DATA__, ingen API,
ingen Playwright). Hvert kort er et ``<a href="/lejebolig/...">`` hvis slug
indeholder adresse + postnr, og hvis tekst indeholder husleje, antal rum og m².

Eksempel på korttekst:
    "Hørparken 7, st. 18. 6000 Kolding  3.895 kr./md.  Ledig nu  1 vær.  41 m²"
Eksempel på slug:
    /lejebolig/hoerparken-7-st-18-6000-kolding/   (postnr = 6000)

Ingen login/venteliste for at se boligerne. Hele Danmark vises, så det fælles
postnr-filter skærer ned til de ønskede bydele.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from boligagent.models import Listing
from .base import BaseScraper
from .parsing import clean_text, parse_kr, parse_m2, parse_rooms

log = logging.getLogger("boligagent.scraper.heimstaden")

LIST_URL = "https://www.heimstaden.dk/ledige-lejeboliger/"
BASE = "https://www.heimstaden.dk"

# postnr + by i slutningen af slug: ...-6000-kolding
_SLUG_POSTNR = re.compile(r"-(\d{4})-[a-z\-]+/?$")
# Adresse i korttekst: efter sagsnr (9-345-18) og op til "{postnr} {By}"
_ADDR_RE = re.compile(
    r"\d+-\d+-\d+\s+(.+?)[.\s]*(\d{4})\s+([A-ZÆØÅ][a-zæøå]+(?:\s[A-ZÆØÅ]{1,3})?)"
)
_RENT_RE = re.compile(r"([\d.]+)\s*kr\.?\s*/?\s*md", re.IGNORECASE)
_AVAIL_RE = re.compile(r"(Ledig\s+nu|\d{2}-\d{2}-\d{4})", re.IGNORECASE)


class HeimstadenScraper(BaseScraper):
    name = "heimstaden"
    source = "Heimstaden"

    def fetch(self) -> list[Listing]:
        from selectolax.lexbor import LexborHTMLParser

        html = self.get(LIST_URL).text
        tree = LexborHTMLParser(html)

        listings: list[Listing] = []
        seen: set[str] = set()
        # Hvert kort er selve <a class="rental-element"> – IKKE en forælder.
        for a in tree.css('a[href*="/lejebolig/"]'):
            href = a.attributes.get("href", "")
            if not href or href in seen:
                continue
            seen.add(href)
            listing = self._card_to_listing(a, href)
            if listing:
                listings.append(listing)
        if not listings:
            log.warning("[heimstaden] 0 kort fundet – layout kan være ændret.")
        return listings

    def _card_to_listing(self, anchor, href: str) -> Optional[Listing]:
        url = href if href.startswith("http") else BASE + href
        text = re.sub(r"\s+", " ", anchor.text()).strip()

        # Postnr fra slug (mest pålideligt)
        postnr = None
        m = _SLUG_POSTNR.search(href)
        if m:
            postnr = int(m.group(1))

        # Adresse fra korttekst, ellers fra slug
        adr_m = _ADDR_RE.search(text)
        if adr_m:
            adresse = clean_text(f"{adr_m.group(1).strip()}, {adr_m.group(2)} {adr_m.group(3)}")
            if postnr is None:
                postnr = int(adr_m.group(2))
        else:
            adresse = _slug_to_address(href)

        rent_m = _RENT_RE.search(text)
        avail_m = _AVAIL_RE.search(text)

        billede = None
        img = anchor.css_first("img")
        if img:
            billede = img.attributes.get("src") or img.attributes.get("data-src")
            if billede and billede.startswith("/"):
                billede = BASE + billede

        return Listing(
            kilde=self.source,
            url=url,
            titel=adresse,
            adresse=adresse,
            postnr=postnr,
            m2=parse_m2(text),
            vaerelser=parse_rooms(text),
            husleje=parse_kr(rent_m.group(0)) if rent_m else None,
            indflytning=clean_text(avail_m.group(1)) if avail_m else None,
            billede_url=billede,
        )


def _slug_to_address(href: str) -> Optional[str]:
    m = re.search(r"/lejebolig/([^/]+)/?", href)
    if not m:
        return None
    parts = m.group(1).replace("-", " ")
    return clean_text(parts.title())
