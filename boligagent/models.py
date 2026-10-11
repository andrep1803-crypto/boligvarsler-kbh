"""Fælles datamodel for en annonce på tværs af alle scrapere."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Listing:
    """En lejebolig-annonce.

    Alle felter undtagen ``kilde``, ``url`` og ``id`` kan være ``None``
    hvis siden ikke oplyser dem. Manglende data gør IKKE at annoncen
    forkastes – den markeres i stedet som "mangler data" i varselet.
    """

    kilde: str                       # f.eks. "Heimstaden"
    url: str                         # direkte link til annoncen
    id: str = ""                     # stabil, unik id (udfyldes automatisk hvis tom)

    titel: Optional[str] = None
    adresse: Optional[str] = None
    postnr: Optional[int] = None
    m2: Optional[int] = None
    vaerelser: Optional[int] = None
    husleje: Optional[int] = None        # kr./md.
    aconto: Optional[int] = None         # aconto/forbrug kr./md. hvis oplyst separat
    depositum: Optional[int] = None
    indflytning: Optional[str] = None    # fritekst, f.eks. "1. december 2026"
    billede_url: Optional[str] = None
    publiceret: Optional[str] = None     # fritekst/ISO hvis oplyst

    def __post_init__(self) -> None:
        if not self.id:
            self.id = self.auto_id()

    def auto_id(self) -> str:
        """Danner en stabil id ud fra kilde + url (eller adresse som reserve)."""
        raw = f"{self.kilde}|{self.url or ''}|{self.adresse or ''}"
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
        return f"{self.kilde.lower()}-{digest}"

    # --- hjælpere ---------------------------------------------------------

    def total_leje(self) -> Optional[int]:
        """Husleje + aconto hvis begge findes, ellers husleje alene."""
        if self.husleje is None:
            return None
        if self.aconto:
            return self.husleje + self.aconto
        return self.husleje

    def mangler_data(self) -> bool:
        """True hvis m², værelser eller pris mangler."""
        return self.m2 is None or self.vaerelser is None or self.husleje is None

    def to_dict(self) -> dict:
        return asdict(self)
