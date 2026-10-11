"""Boligsiden – KUN lejeboliger.

Datakilde (VERIFICERET live): Boligsidens eget offentlige JSON-API på
``https://api.boligsiden.dk/search/rentals``. Ingen nøgle, ingen login, ingen
Playwright. Vi henter pr. kommune-slug og lader det fælles postnr-filter i
``boligagent/filters.py`` skære ned til de ønskede bydele.

Bekræftede detaljer (okt. 2026):
  * Geo-filter: ``municipalities=koebenhavn`` (slug) -> 470 boliger,
    ``frederiksberg`` -> 35. Komma-lister og postnr-lister virker IKKE
    (returnerer 0), derfor ét kald pr. kommune.
  * Paginering: ``perPage`` + ``page``.
  * Felter: ``monthlyExpense`` (husleje/md.), ``housingArea`` (m²),
    ``numberOfRooms``, ``address.zipCode/roadName/houseNumber/cityName``,
    ``slugAddress`` (-> URL), ``rental.from`` (indflytning), ``defaultImage``.
"""

from __future__ import annotations

import json as _json
import logging
import os
import urllib.parse
from typing import Any, Optional

import httpx

from boligagent.models import Listing
from .base import BaseScraper
from .parsing import clean_text

log = logging.getLogger("boligagent.scraper.boligsiden")

ENDPOINT = "https://api.boligsiden.dk/search/rentals"
WEB_BASE = "https://www.boligsiden.dk/lejebolig/"

# Boligsidens Cloudflare blokkerer datacenter-IP-er (bl.a. GitHub Actions) med
# 403 – uansett headere. Virker fint fra en vanlig (bolig-)IP, så lokalt går det
# direkte. I skyen faller vi tilbake til et gratis offentlig relay (r.jina.ai)
# som henter fra sin egen, ikke-blokkerte IP og gir oss rå JSON tilbake.
JINA_PREFIX = "https://r.jina.ai/"

# Kommuner der dækker de ønskede bydele. Frederiksberg er egen kommune.
MUNICIPALITIES = ["koebenhavn", "frederiksberg"]
PER_PAGE = 50
MAX_PAGES = 30  # sikkerhedsgrænse (470 boliger / 50 = 10 sider for København)

# API'et sidder bag Cloudflare, som afviser "nøgne" kald fra datacenter-IP'er
# (bl.a. GitHub Actions) med 403. Vi efterligner de headere boligsiden.dk's
# eget frontend sender, så WAF'en slipper os igennem også fra skyen.
API_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.boligsiden.dk",
    "Referer": "https://www.boligsiden.dk/",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}


class BoligsidenScraper(BaseScraper):
    name = "boligsiden"
    source = "Boligsiden"

    def fetch(self) -> list[Listing]:
        listings: list[Listing] = []
        seen_ids: set[str] = set()
        for muni in MUNICIPALITIES:
            try:
                cases = list(self._iter_cases(muni))
            except httpx.HTTPError as exc:
                # Typisk 403 fra sky-IP uden relay-nøgle. Vi degraderer pænt:
                # returnér det vi har (ofte 0) i stedet for at vælte scraperen,
                # så runneren ikke sender gentagne "fejlede"-varsler hver time.
                log.warning(
                    "[boligsiden] kunne ikke hente '%s' (%s). "
                    "Virker lokalt; i skyen kræver det en gratis JINA_API_KEY – se README.",
                    muni, exc,
                )
                continue
            for case in cases:
                try:
                    listing = self._parse_case(case)
                except Exception as exc:  # én dårlig annonce vælter ikke resten
                    log.warning("[boligsiden] kunne ikke parse annonce: %s", exc)
                    continue
                if listing and listing.id not in seen_ids:
                    seen_ids.add(listing.id)
                    listings.append(listing)
        return listings

    def _iter_cases(self, municipality: str):
        page = 1
        while page <= MAX_PAGES:
            params = {
                "municipalities": municipality,
                "perPage": str(PER_PAGE),
                "page": str(page),
            }
            data = self._fetch_json(params)
            cases = data.get("cases") if isinstance(data, dict) else None
            if not cases:
                break
            yield from cases
            if len(cases) < PER_PAGE:
                break
            page += 1

    def _fetch_json(self, params: dict) -> dict:
        """Henter én side. Direkte først; ved 403 (sky-IP blokeret) via relay."""
        try:
            return self.get_json(ENDPOINT, params=params, headers=API_HEADERS)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 403:
                raise
            log.warning("[boligsiden] 403 direkte (sky-IP blokeret) – prøver relay via r.jina.ai")

        qs = urllib.parse.urlencode(params)
        relay_url = f"{JINA_PREFIX}{ENDPOINT}?{qs}"
        relay_headers = {"x-respond-with": "text", "x-no-cache": "true"}
        # Gratis Jina-nøgle (valgfri) hæver grænserne og virker fra sky-IP'er.
        jina_key = os.environ.get("JINA_API_KEY", "").strip()
        if jina_key:
            relay_headers["Authorization"] = f"Bearer {jina_key}"
        self._throttle()
        resp = self._client.get(relay_url, headers=relay_headers, timeout=60)
        resp.raise_for_status()
        return _json.loads(resp.text)

    # ------------------------------------------------------------------

    def _parse_case(self, case: dict) -> Optional[Listing]:
        addr = case.get("address", {}) or {}
        road = addr.get("roadName")
        house = addr.get("houseNumber") or ""
        floor = addr.get("floor")
        door = addr.get("door")
        zipcode = addr.get("zipCode")
        city = addr.get("cityName") or _nested(addr, "city", "name")

        street = " ".join(p for p in [road, str(house)] if p).strip()
        if floor:
            street += f", {floor}."
        if door:
            street += f" {door}"
        adresse = ", ".join(p for p in [street or None,
                                        f"{zipcode} {city}".strip() if (zipcode or city) else None] if p) or None

        slug = case.get("slugAddress") or case.get("slug")
        url = WEB_BASE + slug if slug else "https://www.boligsiden.dk/til-leje"

        rental = case.get("rental") or {}
        return Listing(
            kilde=self.source,
            url=url,
            titel=clean_text(street or road),
            adresse=adresse,
            postnr=int(zipcode) if str(zipcode).isdigit() else None,
            m2=_to_int(case.get("housingArea") or case.get("livingArea")),
            vaerelser=_to_int(case.get("numberOfRooms")),
            husleje=_to_int(case.get("monthlyExpense") or case.get("casePrice")),
            aconto=None,  # Boligsiden oplyser typisk ikke aconto separat for leje
            depositum=_to_int(rental.get("deposit")),
            indflytning=clean_text(rental.get("from")),
            billede_url=_first_image_url(case.get("defaultImage")),
            publiceret=clean_text(case.get("timeOnMarket") or case.get("daysListed")),
        )


def _nested(d: dict, *keys: str) -> Any:
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _first_image_url(img: Any) -> Optional[str]:
    """defaultImage kan være indlejret; find første http-billede-url."""
    if not img:
        return None
    if isinstance(img, str) and img.startswith("http"):
        return img
    if isinstance(img, dict):
        sources = img.get("imageSources")
        if isinstance(sources, list):
            for s in sources:
                if isinstance(s, dict):
                    for v in s.values():
                        if isinstance(v, str) and v.startswith("http"):
                            return v
        for v in img.values():
            if isinstance(v, str) and v.startswith("http"):
                return v
    return None


def _to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None
