"""Findbolig.nu – almene boliger i hovedstadsområdet.

Fund (live, Fase 1):
  * Serveren har en ufuldstændig SSL-certifikatkæde (manglende mellemcertifikat),
    så almindelige klienter afviser forbindelsen. Kan omgås, men er et dårligt tegn.
  * Oversigtssiden ``/da/ledigeboliger.aspx`` er en ASP.NET-side hvor resultaterne
    hentes via postback/filtre – ingen simple annonce-links i rå HTML.
  * VIGTIGT: Findbolig er almene boliger. For reelt at kunne få en bolig kræves
    medlemskab + anciennitet på venteliste ("opskrivning"). Siden har desuden sin
    EGEN søgeagent med e-mailvarsel.

Anbefaling: Brug Findboligs egen søgeagent (e-mailvarsel) i stedet for at scrape.
Den er gratis at oprette og rammer præcis det samme – uden SSL/postback-bøvl.

Status: IKKE aktiv som scraper. Returnerer en tom liste (fejler ikke).
"""

from __future__ import annotations

import logging

from boligagent.models import Listing
from .base import BaseScraper

log = logging.getLogger("boligagent.scraper.findbolig")


class FindboligScraper(BaseScraper):
    name = "findbolig"
    source = "Findbolig"

    def fetch(self) -> list[Listing]:
        log.info("[findbolig] ikke aktiv (SSL-kæde + postback + kræver opskrivning). "
                 "Anbefaling: brug Findboligs egen e-mail-søgeagent. Returnerer 0.")
        return []
