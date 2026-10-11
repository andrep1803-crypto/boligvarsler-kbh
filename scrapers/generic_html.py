"""Generisk HTML-kort-parser som flere simple sider kan dele.

Mange mindre udlejeres sider viser boliger som en liste af "kort" – et
gentaget element (ofte et <a> eller en div med et link indeni) der indeholder
adresse, m², værelser og pris som tekst. Denne hjælper finder sådanne kort ud
fra en CSS-selector og trækker felterne ud med regex-hjælperne.

Hver konkret scraper angiver bare sin LIST_URL, en CSS-selector til kortene og
(valgfrit) selektorer til enkeltfelter. Det gør siderne nemme at vedligeholde:
når layoutet ændrer sig, retter du kun selektoren.
"""

from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import urljoin

from boligagent.models import Listing
from .base import BaseScraper
from .parsing import clean_text, parse_kr, parse_m2, parse_rooms, parse_postnr

log = logging.getLogger("boligagent.scraper.generic")


class GenericHtmlScraper(BaseScraper):
    """Subklasser sætter mindst LIST_URL, CARD_SELECTOR og BASE_URL."""

    LIST_URL: str = ""
    BASE_URL: str = ""
    CARD_SELECTOR: str = ""          # f.eks. ".property-card" eller "a.listing"
    LINK_SELECTOR: Optional[str] = None  # hvis linket er et barn af kortet

    def fetch(self) -> list[Listing]:
        if not self.LIST_URL or not self.CARD_SELECTOR:
            log.warning("[%s] LIST_URL/CARD_SELECTOR ikke sat – scraper skal færdiggøres.", self.name)
            return []
        from selectolax.lexbor import LexborHTMLParser

        html = self.get(self.LIST_URL).text
        tree = LexborHTMLParser(html)
        out: list[Listing] = []
        for card in tree.css(self.CARD_SELECTOR):
            listing = self._card_to_listing(card)
            if listing:
                out.append(listing)

        # dedup på url
        seen: set[str] = set()
        unique: list[Listing] = []
        for l in out:
            if l.url not in seen:
                seen.add(l.url)
                unique.append(l)
        if not unique:
            log.info("[%s] 0 kort fundet med selector '%s' – tjek selektoren.",
                     self.name, self.CARD_SELECTOR)
        return unique

    def _card_to_listing(self, card) -> Optional[Listing]:
        # Link
        link_node = card
        if self.LINK_SELECTOR:
            link_node = card.css_first(self.LINK_SELECTOR) or card
        href = link_node.attributes.get("href") if link_node else None
        if not href and card.tag == "a":
            href = card.attributes.get("href")
        if not href:
            a = card.css_first("a[href]")
            href = a.attributes.get("href") if a else None
        if not href:
            return None
        url = href if href.startswith("http") else urljoin(self.BASE_URL or self.LIST_URL, href)

        text = card.text(separator=" ", strip=True)
        img = card.css_first("img")
        billede = None
        if img:
            billede = img.attributes.get("src") or img.attributes.get("data-src")
            if billede and billede.startswith("/"):
                billede = urljoin(self.BASE_URL or self.LIST_URL, billede)

        return Listing(
            kilde=self.source,
            url=url,
            titel=clean_text(text[:120]) if text else None,
            adresse=clean_text(text[:120]) if text else None,
            postnr=parse_postnr(text),
            m2=parse_m2(text),
            vaerelser=parse_rooms(text),
            husleje=parse_kr(text),
            billede_url=billede,
        )
