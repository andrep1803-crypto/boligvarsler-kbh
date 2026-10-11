"""Filtrering af annoncer mod kriterierne i config.yaml.

Reglen fra brief'et: mangler en annonce m², værelser eller pris, bliver den
IKKE forkastet. Den sendes med markeringen "mangler data" så du selv kan vurdere.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .models import Listing
from scrapers.parsing import er_moebleret_tekst


@dataclass
class Area:
    navn: str
    postnr_ranges: list[tuple[int, int]]
    navne: list[str]


def parse_areas(cfg: dict[str, Any]) -> list[Area]:
    areas: list[Area] = []
    for item in cfg.get("omraader", []):
        ranges = [tuple(r) for r in item.get("postnr", [])]
        areas.append(
            Area(
                navn=item["navn"],
                postnr_ranges=ranges,
                navne=[n.lower() for n in item.get("navne", [])],
            )
        )
    return areas


def _postnr_match(postnr: int, areas: list[Area]) -> Optional[str]:
    for area in areas:
        for lo, hi in area.postnr_ranges:
            if lo <= postnr <= hi:
                return area.navn
    return None


def _navn_match(listing: Listing, areas: list[Area]) -> Optional[str]:
    hay = " ".join(
        filter(None, [listing.adresse or "", listing.titel or ""])
    ).lower()
    for area in areas:
        for kw in area.navne:
            if kw and kw in hay:
                return area.navn
    return None


def match_area(listing: Listing, areas: list[Area]) -> Optional[str]:
    """Returnerer områdenavn hvis annoncen ligger i et ønsket område.

    Postnummer har forrang. Mangler postnummer, bruges bydelsnavn som reserve.
    Returnerer None hvis annoncen ikke kan placeres i et ønsket område
    (men kun hvis vi faktisk HAR info at matche på – se passes_filters).
    """
    if listing.postnr is not None:
        return _postnr_match(listing.postnr, areas)
    return _navn_match(listing, areas)


@dataclass
class FilterResult:
    passed: bool
    area: Optional[str]
    reason: str  # kort forklaring (til log/test-mode)


def passes_filters(listing: Listing, cfg: dict[str, Any], areas: list[Area]) -> FilterResult:
    k = cfg["kriterier"]
    min_m2 = k["min_m2"]
    min_rooms = k["min_vaerelser"]
    max_rent = k["maks_husleje"]
    include_aconto = k.get("medregn_aconto_i_filter", True)

    # --- Område ---
    area = match_area(listing, areas)
    has_location_info = listing.postnr is not None or listing.adresse or listing.titel
    if area is None and has_location_info:
        # Vi kunne placere annoncen, men den er udenfor ønskede områder.
        return FilterResult(False, None, "udenfor område")
    # Hvis vi slet ingen stedinfo har, lader vi den gå videre som "mangler data".

    # --- Møbleret? Slå fra hvis brugeren ikke vil have møblerede boliger. ---
    if k.get("ekskluder_moebleret", False):
        # Struktureret flag (fx BoligPortal) har forrang; ellers læs af titlen.
        if listing.moebleret is True or (
            listing.moebleret is None and er_moebleret_tekst(listing.titel, listing.adresse)
        ):
            return FilterResult(False, area, "møbleret")

    # --- Numeriske kriterier. Manglende værdi => consider kravet opfyldt (vis med advarsel). ---
    if listing.m2 is not None and listing.m2 < min_m2:
        return FilterResult(False, area, f"for lille ({listing.m2} m²)")

    if listing.vaerelser is not None and listing.vaerelser < min_rooms:
        return FilterResult(False, area, f"for få værelser ({listing.vaerelser})")

    if listing.husleje is not None:
        rent_to_check = listing.total_leje() if include_aconto else listing.husleje
        if rent_to_check is not None and rent_to_check > max_rent:
            label = "husleje+aconto" if (include_aconto and listing.aconto) else "husleje"
            return FilterResult(False, area, f"for dyr ({rent_to_check} kr. {label})")

    reason = "mangler data – vises til manuel vurdering" if listing.mangler_data() else "match"
    return FilterResult(True, area, reason)
