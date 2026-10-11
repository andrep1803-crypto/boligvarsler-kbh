"""Formatering af Telegram-beskeder og udsendelse af varsler + søknadstekst."""

from __future__ import annotations

import html
import logging
import os
from pathlib import Path
from typing import Optional

from .config import Secrets
from .models import Listing
from .telegram import Telegram

log = logging.getLogger("boligagent.notifier")

ROOT = Path(__file__).resolve().parent.parent
SOKNAD_PATH = ROOT / "soknad.txt"


def _esc(value: object) -> str:
    return html.escape(str(value))


def _kr(value: Optional[int]) -> str:
    if value is None:
        return "?"
    return f"{value:,}".replace(",", ".") + " kr."


def format_listing(listing: Listing, area: Optional[str]) -> str:
    """Bygger HTML-teksten til ét boligvarsel."""
    lines: list[str] = []
    titel = listing.titel or listing.adresse or "Lejebolig"
    lines.append(f"🏠 <b>{_esc(titel)}</b>")
    lines.append(f"📍 Kilde: {_esc(listing.kilde)}")

    if listing.adresse:
        lines.append(f"🗺️ Adresse: {_esc(listing.adresse)}")
    bydel = area or (f"postnr {listing.postnr}" if listing.postnr else None)
    if bydel:
        lines.append(f"🏙️ Bydel: {_esc(bydel)}")

    storrelse = []
    if listing.m2 is not None:
        storrelse.append(f"{listing.m2} m²")
    if listing.vaerelser is not None:
        storrelse.append(f"{listing.vaerelser} vær.")
    if storrelse:
        lines.append("📐 " + " · ".join(storrelse))

    # Husleje (+ aconto)
    if listing.husleje is not None:
        if listing.aconto:
            total = listing.total_leje()
            lines.append(
                f"💰 Husleje: {_kr(listing.husleje)} + aconto {_kr(listing.aconto)} "
                f"= {_kr(total)}/md."
            )
        else:
            lines.append(f"💰 Husleje: {_kr(listing.husleje)}/md.")
    if listing.depositum is not None:
        lines.append(f"🔒 Depositum: {_kr(listing.depositum)}")
    if listing.indflytning:
        lines.append(f"📅 Indflytning: {_esc(listing.indflytning)}")

    if listing.mangler_data():
        lines.append("⚠️ <b>mangler data</b> – tjek selv annoncen")

    lines.append(f'🔗 <a href="{_esc(listing.url)}">Se annoncen</a>')
    return "\n".join(lines)


def load_soknad(secrets: Secrets, path: Path = SOKNAD_PATH) -> str:
    """Indlæser søknadsteksten og indsætter kontaktinfo fra secrets.

    Den personlige tekst hentes helst fra miljøvariablen ``SOKNAD_TEKST``
    (en GitHub Secret), så den ikke behøver ligge i koden. ``\\n`` i secreten
    tolkes som linjeskift. Mangler den, bruges den generiske ``soknad.txt``.
    """
    env_text = os.environ.get("SOKNAD_TEKST", "").strip()
    if env_text:
        text = env_text.replace("\\n", "\n")
    else:
        text = path.read_text(encoding="utf-8")
    return (
        text.replace("{KONTAKT_NAVN}", secrets.kontakt_navn or "")
        .replace("{KONTAKT_TLF}", secrets.kontakt_tlf or "")
        .replace("{KONTAKT_ADRESSE}", secrets.kontakt_adresse or "")
    )


class Notifier:
    def __init__(self, telegram: Telegram, secrets: Secrets):
        self.tg = telegram

    def notify_listing(self, listing: Listing, area: Optional[str]) -> None:
        caption = format_listing(listing, area)
        if listing.billede_url:
            self.tg.send_photo(listing.billede_url, caption)
        else:
            self.tg.send_message(caption)
        # (Søknadsteksten sendes IKKE længere – du får kun selve boligannoncen.)

    def notify_summary(self, total: int, per_kilde: dict[str, int]) -> None:
        lines = [f"✅ <b>Boligvarsler er sat op.</b>",
                 f"Første kørsel: registrerede {total} eksisterende annoncer (ingen varsler sendt)."]
        if per_kilde:
            lines.append("")
            for kilde, n in sorted(per_kilde.items()):
                lines.append(f"• {_esc(kilde)}: {n}")
        lines.append("")
        lines.append("Fra næste kørsel får du besked om <b>nye</b> boliger der matcher.")
        self.tg.send_message("\n".join(lines), disable_preview=True)

    def notify_scraper_error(self, scraper: str, fails: int, error: str) -> None:
        self.tg.send_message(
            f"⚠️ <b>Scraper-fejl</b>\n"
            f"'{_esc(scraper)}' har fejlet {fails} gange i træk.\n"
            f"Seneste fejl: {_esc(error[:300])}",
            disable_preview=True,
        )
