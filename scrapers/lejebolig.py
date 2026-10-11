"""Lejebolig.dk – https://www.lejebolig.dk/

Datakilde (VERIFICERET live, okt. 2026): Søgeresultatet er server-renderet HTML.
Hver annonce er et ``<div class="lease-item">`` (dummy-kort med klassen
``dummy`` springes over). Kortet rummer:
  * ``a[href*="/lejebolig/<id>/..."]`` – link til annoncen
  * ``h2`` – titel (ofte med gade/størrelse)
  * ``.lease-sub-header`` – fx "Lejlighed på Østerbro" (indeholder bydelen)
  * ``.rent`` – husleje, fx "15.600,-"
  * ``.lease-spec`` (i rækkefølge) – [0] m², [1] antal værelser, [2] lejeperiode

Vigtige detaljer:
  * Listesiden viser IKKE postnummer. Vi henter derfor én side pr. bydel via
    bydels-URL'er, så bydelen er kendt på forhånd. Bydelsnavnet står også i
    ``.lease-sub-header`` → det fælles navne-match i ``boligagent/filters.py``
    placerer annoncen i rigtigt område (postnr sættes ikke – det er skjult).
  * Standard-sortering er "Nyeste øverst", så nye annoncer ligger altid på
    første side. Vi henter kun første side pr. bydel (skånsomt: 5 kald/kørsel).
  * ``Christianshavn`` har ingen egen bydels-URL men dækkes af ``koebenhavn-k``.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from boligagent.models import Listing
from .base import BaseScraper
from .parsing import clean_text, parse_kr

log = logging.getLogger("boligagent.scraper.lejebolig")

BASE = "https://www.lejebolig.dk"
# Standard-sortering er allerede "Nyeste øverst" – ingen sort-param nødvendig.
BYDEL_PATH = BASE + "/lejeboliger/koebenhavn/alle-vaerelser/"
# Bydels-slugs der dækker de ønskede områder. frederiksberg dækker også
# Frederiksberg C; koebenhavn-k dækker Christianshavn/Indre By.
BYDELE = [
    "koebenhavn-k",
    "koebenhavn-v",
    "koebenhavn-n",
    "koebenhavn-oe",
    "frederiksberg",
]

_IMG_RE = re.compile(r"url\((['\"]?)(https?://[^'\")]+)\1\)")


class LejeboligScraper(BaseScraper):
    name = "lejebolig"
    source = "Lejebolig"

    def fetch(self) -> list[Listing]:
        from selectolax.lexbor import LexborHTMLParser

        listings: list[Listing] = []
        seen_ids: set[str] = set()
        for slug in BYDELE:
            html = self.get(BYDEL_PATH + slug).text
            tree = LexborHTMLParser(html)
            cards = [
                c for c in tree.css("div.lease-item")
                if "dummy" not in (c.attributes.get("class") or "")
            ]
            for card in cards:
                try:
                    listing = self._parse(card)
                except Exception as exc:  # én dårlig annonce vælter ikke resten
                    log.warning("[lejebolig] kunne ikke parse annonce: %s", exc)
                    continue
                if listing and listing.id not in seen_ids:
                    seen_ids.add(listing.id)
                    listings.append(listing)
        if not listings:
            log.warning("[lejebolig] 0 annoncer fundet – layout kan være ændret.")
        return listings

    def _parse(self, card) -> Optional[Listing]:
        a = card.css_first('a[href*="/lejebolig/"]')
        href = a.attributes.get("href") if a else None
        if not href or not re.search(r"/lejebolig/\d+/", href):
            return None
        url = href if href.startswith("http") else BASE + href

        h2 = card.css_first("h2")
        titel = clean_text(h2.text()) if h2 else None
        sub = card.css_first(".lease-sub-header")
        subt = clean_text(sub.text()) if sub else None

        rent_node = card.css_first(".rent")
        husleje = parse_kr(rent_node.text()) if rent_node else None

        specs = [clean_text(s.text()) for s in card.css(".lease-spec")]
        m2 = _first_int(specs[0]) if len(specs) >= 1 else None
        vaerelser = _first_int(specs[1]) if len(specs) >= 2 else None

        billede = None
        img = card.css_first(".lease-image")
        if img:
            m = _IMG_RE.search(img.attributes.get("style", ""))
            if m:
                billede = m.group(2)

        return Listing(
            kilde=self.source,
            url=url,
            titel=titel,
            # Bydelen i sub-header driver områdematch (postnr er skjult på listen).
            adresse=subt or titel,
            postnr=None,
            m2=m2,
            vaerelser=vaerelser,
            husleje=husleje,
            billede_url=billede,
        )


def _first_int(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    m = re.search(r"\d+", text)
    return int(m.group(0)) if m else None
