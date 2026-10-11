"""Orkestrering: kør scrapere, filtrér, afdup, varsl."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from .config import Secrets, load_config, load_secrets
from .filters import Area, FilterResult, parse_areas, passes_filters
from .models import Listing
from .notifier import Notifier
from .storage import FailureStore, SeenStore
from .telegram import Telegram

log = logging.getLogger("boligagent.runner")


@dataclass
class Hit:
    listing: Listing
    area: Optional[str]


def build_context(cfg: dict):
    from scrapers.base import ScrapeContext
    h = cfg.get("hentning", {})
    return ScrapeContext(
        user_agent=h.get("user_agent", "Mozilla/5.0"),
        delay_seconds=float(h.get("forsinkelse_sekunder", 2)),
        timeout_seconds=float(h.get("timeout_sekunder", 30)),
    )


def active_scrapers(cfg: dict):
    from scrapers import REGISTRY
    ctx = build_context(cfg)
    enabled = cfg.get("kilder", {})
    for key, cls in REGISTRY.items():
        if enabled.get(key, True):
            yield cls(ctx)


def collect_listings(cfg: dict, fails: FailureStore, notifier: Optional[Notifier]) -> list[Listing]:
    """Kører alle aktive scrapere robust. Én sides fejl stopper ikke resten."""
    fejl_graense = int(cfg.get("fejl_graense", 3))
    all_listings: list[Listing] = []
    for scraper in active_scrapers(cfg):
        try:
            with scraper:
                found = scraper.fetch()
            log.info("[%s] %d annoncer hentet.", scraper.name, len(found))
            all_listings.extend(found)
            fails.record_success(scraper.name)
        except Exception as exc:  # noqa: BLE001 – robust: log + fortsæt
            count = fails.record_failure(scraper.name)
            log.error("[%s] fejlede (%d i træk): %s", scraper.name, count, exc)
            if count >= fejl_graense and notifier is not None:
                notifier.notify_scraper_error(scraper.name, count, str(exc))
    return all_listings


def evaluate(listings: list[Listing], cfg: dict, areas: list[Area]) -> list[Hit]:
    """Returnerer de annoncer der passer kriterierne."""
    hits: list[Hit] = []
    for listing in listings:
        result: FilterResult = passes_filters(listing, cfg, areas)
        if result.passed:
            hits.append(Hit(listing, result.area))
        else:
            log.debug("[%s] droppet: %s (%s)", listing.kilde, listing.titel, result.reason)
    return hits


def run(test_mode: bool = False) -> int:
    cfg = load_config()
    areas = parse_areas(cfg)
    secrets = load_secrets()

    fails = FailureStore()
    seen = SeenStore()

    # Notifier kun hvis Telegram er sat op og vi ikke er i test-mode.
    notifier: Optional[Notifier] = None
    if secrets.telegram_ready and not test_mode:
        tg = Telegram(secrets.telegram_bot_token, secrets.telegram_chat_id)
        notifier = Notifier(tg, secrets)
    elif not secrets.telegram_ready and not test_mode:
        log.warning("Telegram ikke konfigureret – kører uden at sende varsler.")

    listings = collect_listings(cfg, fails, notifier)
    hits = evaluate(listings, cfg, areas)
    log.info("I alt %d annoncer, %d matcher kriterierne.", len(listings), len(hits))

    # --- TEST-MODE: bare print, gem intet, send intet ---
    if test_mode:
        _print_test_report(listings, hits)
        return 0

    # --- FØRSTE KØRSEL: registrér alt, send kun én opsummering ---
    if seen.is_first_run:
        per_kilde: dict[str, int] = {}
        for hit in hits:
            seen.add(hit.listing.id)
            per_kilde[hit.listing.kilde] = per_kilde.get(hit.listing.kilde, 0) + 1
        # registrér også ikke-matchende, så de ikke popper op som "nye" senere
        for listing in listings:
            seen.add(listing.id)
        seen.save()
        fails.save()
        if notifier:
            notifier.notify_summary(len(hits), per_kilde)
        log.info("Første kørsel: %d matchende registreret uden varsel.", len(hits))
        return 0

    # --- NORMAL KØRSEL: varsl om nye matches ---
    nye = [h for h in hits if not seen.has(h.listing.id)]
    log.info("%d nye matchende annoncer.", len(nye))
    for hit in nye:
        if notifier:
            notifier.notify_listing(hit.listing, hit.area)
        seen.add(hit.listing.id)
    # registrér også nye ikke-matchende annoncer så de ikke tæller som nye igen
    for listing in listings:
        seen.add(listing.id)

    seen.save()
    fails.save()
    return 0


def _print_test_report(listings: list[Listing], hits: list[Hit]) -> None:
    print("\n" + "=" * 70)
    print(f"TEST-MODE: {len(listings)} annoncer hentet, {len(hits)} matcher kriterierne")
    print("=" * 70)
    by_source: dict[str, int] = {}
    for l in listings:
        by_source[l.kilde] = by_source.get(l.kilde, 0) + 1
    print("\nHentet pr. kilde:")
    for kilde, n in sorted(by_source.items()):
        print(f"  {kilde:16} {n}")
    print(f"\nMatcher kriterierne ({len(hits)}):")
    if not hits:
        print("  (ingen)")
    for hit in hits:
        l = hit.listing
        flag = " ⚠️ mangler data" if l.mangler_data() else ""
        rent = l.total_leje()
        print(f"  • [{l.kilde}] {l.titel or l.adresse or '?'} "
              f"| {l.m2 or '?'} m² | {l.vaerelser or '?'} vær. "
              f"| {rent or '?'} kr. | {hit.area or '?'}{flag}")
        print(f"    {l.url}")
    print("=" * 70 + "\n")
