"""BoligPortal – https://www.boligportal.dk/lejeboliger/

Datakilde (VERIFICERET live, okt. 2026): Søgeresultatet er server-renderet og
ligger som indlejret JSON i et ``<script>`` med formen::

    {"component": "SearchResultApp", "props": {"page_props": {...}}}

Ingen separat API/GraphQL, ingen login, ingen Playwright. ``page_props`` har
``results`` (liste af annoncer) og ``next_page_url`` til paginering.

Vigtige detaljer:
  * Bydels-dækning: slug'en ``/lejeboliger/københavn/`` (city_level_1=københavn)
    dækker HELE Storkøbenhavn inkl. Frederiksberg (postnr 1800-2000). En separat
    Frederiksberg-søgning gav 0 og er unødvendig. Det fælles postnr-filter i
    ``boligagent/filters.py`` skærer ned til de ønskede bydele.
  * Sortering: ``order=-advertised_date`` VIRKER og giver nyeste først. Derfor
    behøver vi ikke scanne alle ~1000 annoncer hver gang – nye annoncer ligger
    altid øverst. Vi henter de nyeste ``MAX_PAGES`` sider.
  * Sidestørrelse: ``limit`` maks. 100 pr. side.
  * ``rooms``-feltet er upålideligt (viser nogle gange antal soveværelser, fx
    1 for en "2-værelses"). Vi læser derfor værelsestallet fra titlen først og
    falder tilbage til ``rooms``-feltet.
  * Adresse: ``formatted_address``/``display_address`` er ofte null (skjult til
    kontakt). Vi bygger adressen af street_name/street_number/postal_code/city.

Felter pr. annonce: id, url (relativ), category, title, street_name,
street_number, postal_code, city, rooms, size_m2, monthly_rent,
monthly_rent_extra_costs, deposit, available_from, advertised_date, images.
"""

from __future__ import annotations

import json as _json
import logging
import os
import re
from typing import Any, Optional

import httpx

from boligagent.models import Listing
from .base import BaseScraper
from .parsing import clean_text, er_moebleret_tekst, parse_rooms

log = logging.getLogger("boligagent.scraper.boligportal")

BASE = "https://www.boligportal.dk"

# BoligPortal sidder bag Cloudflare, som blokkerer datacenter-IP-er (bl.a.
# GitHub Actions) med 403 – akkurat som Boligsiden. Virker fint fra en vanlig
# (bolig-)IP, så lokalt går det direkte. I skyen faller vi tilbake til et gratis
# offentlig relay (r.jina.ai) som henter fra sin egen, ikke-blokkerte IP og gir
# oss rå HTML tilbake (inkl. den innbygde SearchResultApp-JSON-en).
JINA_PREFIX = "https://r.jina.ai/"
# city_level_1=københavn dækker hele Storkøbenhavn inkl. Frederiksberg.
LIST_URL = (
    BASE + "/lejeboliger/k%C3%B8benhavn/"
    "?categories=rental_apartment"
    "&min_size_m2=50"
    "&max_monthly_rent=16000"
    "&limit=100"
    "&order=-advertised_date"
)

# Nyeste-først betyder nye annoncer altid ligger øverst. 4 sider (400 nyeste)
# dækker rigeligt selv et langt interval mellem kørsler – uden at scanne alle
# ~1000 annoncer hver gang (skånsomt mod siden ved 10-min-kørsel).
MAX_PAGES = 4

_SCRIPT_RE = re.compile(r'(\{"component":\s*"SearchResultApp".*?\})\s*</script>', re.S)


class BoligPortalScraper(BaseScraper):
    name = "boligportal"
    source = "BoligPortal"

    def fetch(self) -> list[Listing]:
        listings: list[Listing] = []
        seen_ids: set[str] = set()
        url: Optional[str] = LIST_URL
        pages = 0
        while url and pages < MAX_PAGES:
            try:
                pp = self._fetch_page(url)
            except httpx.HTTPError as exc:
                # Typisk 403 fra sky-IP uten relay-nøgle. Vi degraderer pænt:
                # returnér det vi har (ofte 0) i stedet for at vælte scraperen,
                # så runneren ikke sender gentagne "fejlede"-varsler.
                log.warning(
                    "[boligportal] kunne ikke hente side (%s). "
                    "Virker lokalt; i skyen kræver det en gratis JINA_API_KEY – se README.",
                    exc,
                )
                break
            if pp is None:
                break
            results = pp.get("results") or []
            for raw in results:
                try:
                    listing = self._parse(raw)
                except Exception as exc:  # én dårlig annonce vælter ikke resten
                    log.warning("[boligportal] kunne ikke parse annonce: %s", exc)
                    continue
                if listing and listing.id not in seen_ids:
                    seen_ids.add(listing.id)
                    listings.append(listing)
            nxt = pp.get("next_page_url")
            url = (BASE + nxt) if nxt else None
            pages += 1
        if not listings:
            log.warning("[boligportal] 0 annoncer fundet – layout kan være ændret.")
        return listings

    def _fetch_page(self, url: str) -> Optional[dict]:
        html = self._get_html(url)
        m = _SCRIPT_RE.search(html)
        if not m:
            log.warning("[boligportal] fandt ikke SearchResultApp-JSON på %s", url)
            return None
        try:
            return _json.loads(m.group(1))["props"]["page_props"]
        except (ValueError, KeyError) as exc:
            log.warning("[boligportal] kunne ikke læse page_props: %s", exc)
            return None

    def _get_html(self, url: str) -> str:
        """Henter én side som rå HTML. Direkte først; ved 403 (sky-IP
        blokeret) via relay, så den innbygde JSON-en overlever."""
        try:
            return self.get(url).text
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 403:
                raise
            log.warning("[boligportal] 403 direkte (sky-IP blokeret) – prøver relay via r.jina.ai")

        relay_url = f"{JINA_PREFIX}{url}"
        # X-Return-Format: html bevarer <script>-blokken (ellers får vi markdown).
        relay_headers = {"X-Return-Format": "html", "x-no-cache": "true"}
        jina_key = os.environ.get("JINA_API_KEY", "").strip()
        if jina_key:
            relay_headers["Authorization"] = f"Bearer {jina_key}"
        self._throttle()
        resp = self._client.get(relay_url, headers=relay_headers, timeout=60)
        resp.raise_for_status()
        return resp.text

    def _parse(self, raw: dict) -> Optional[Listing]:
        rel = raw.get("url")
        if not rel:
            return None
        url = rel if rel.startswith("http") else BASE + rel

        street = " ".join(
            p for p in [raw.get("street_name"), raw.get("street_number")] if p
        ).strip()
        postnr = _to_int(raw.get("postal_code"))
        city = raw.get("city")
        adresse = (
            raw.get("formatted_address")
            or raw.get("display_address")
            or ", ".join(
                p for p in [street or None,
                            f"{postnr} {city}".strip() if (postnr or city) else None]
                if p
            )
            or None
        )

        title = clean_text(raw.get("title"))
        # rooms-feltet er upålideligt; foretræk værelsestal fra titlen.
        vaerelser = parse_rooms(title) or _to_int(raw.get("rooms"))

        images = raw.get("images") or []
        billede = images[0].get("url") if images and isinstance(images[0], dict) else None

        bp_id = raw.get("id")
        listing_id = f"boligportal-{bp_id}" if bp_id else ""

        # BoligPortal har et struktureret møbel-flag under features.furnished.
        feats = raw.get("features") or {}
        moebleret = feats.get("furnished")
        if moebleret is None:  # reserve: læs det af titlen
            moebleret = er_moebleret_tekst(title) or None

        return Listing(
            kilde=self.source,
            url=url,
            id=listing_id,
            titel=title or clean_text(street),
            adresse=clean_text(adresse),
            postnr=postnr,
            m2=_to_int(raw.get("size_m2")),
            vaerelser=vaerelser,
            husleje=_to_int(raw.get("monthly_rent")),
            aconto=_to_int(raw.get("monthly_rent_extra_costs")),
            depositum=_to_int(raw.get("deposit")),
            indflytning=clean_text(raw.get("available_from")),
            billede_url=billede,
            publiceret=clean_text(raw.get("advertised_date")),
            moebleret=moebleret,
        )


def _to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None
