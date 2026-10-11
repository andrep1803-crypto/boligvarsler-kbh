"""Hjælpefunktioner til at trække tal ud af dansk annoncetekst.

Robuste mod formater som "1.250 kr.", "12.500,-", "87 m²", "3 vær.", "2100 Ø".
Returnerer None når intet kan findes – så annoncen markeres "mangler data".
"""

from __future__ import annotations

import re
from typing import Optional


def parse_kr(text: Optional[str]) -> Optional[int]:
    """Trækker et kronebeløb ud. '12.500 kr./md' -> 12500."""
    if not text:
        return None
    # Fjern tusind-separatorer (punktum) og normalisér
    cleaned = text.replace("\xa0", " ")
    m = re.search(r"(\d{1,3}(?:[.\s]\d{3})+|\d{3,6})", cleaned)
    if not m:
        return None
    digits = re.sub(r"[.\s]", "", m.group(1))
    try:
        val = int(digits)
    except ValueError:
        return None
    # Undgå at opfange åbenlyst forkerte tal (f.eks. postnr 4-cifret < 1000? ok)
    return val if val > 0 else None


def parse_m2(text: Optional[str]) -> Optional[int]:
    """'87 m²' / '87 m2' / '87 kvm' -> 87."""
    if not text:
        return None
    m = re.search(r"(\d{1,4})\s*(?:m²|m2|kvm|m\^?2)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def parse_rooms(text: Optional[str]) -> Optional[int]:
    """'3 værelser' / '3 vær.' / '3-værelses' -> 3."""
    if not text:
        return None
    m = re.search(r"(\d{1,2})[\s-]*(?:vær|rum|rooms?)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def parse_postnr(text: Optional[str]) -> Optional[int]:
    """Finder et dansk 4-cifret postnummer (1000-9999) i teksten."""
    if not text:
        return None
    for m in re.finditer(r"\b(\d{4})\b", text):
        val = int(m.group(1))
        if 1000 <= val <= 9999:
            return val
    return None


def clean_text(text: object) -> Optional[str]:
    if text is None or not isinstance(text, str):
        return None
    return re.sub(r"\s+", " ", text).strip() or None


# "umøbleret"/"ikke møbleret"/"unfurnished" betyder IKKE møbleret – de må ikke
# udløse møbel-filteret. Vi tjekker negationerne først.
_UMOEBLERET_RE = re.compile(r"u-?m[øo]bl|ikke\s+m[øo]bl|uden\s+m[øo]bl|unfurnished", re.IGNORECASE)
_MOEBLERET_RE = re.compile(r"m[øo]bl|furnish", re.IGNORECASE)


def er_moebleret_tekst(*tekster: Optional[str]) -> bool:
    """Gætter ud fra fritekst (titel/beskrivelse) om en bolig er møbleret.

    Returnerer True kun hvis teksten nævner møblering OG ikke er en negation
    som "umøbleret"/"ikke møbleret". Bruges som reserve for sider uden et
    struktureret møbel-felt.
    """
    blob = " ".join(t for t in tekster if t)
    if not blob:
        return False
    if _UMOEBLERET_RE.search(blob):
        return False
    return bool(_MOEBLERET_RE.search(blob))
