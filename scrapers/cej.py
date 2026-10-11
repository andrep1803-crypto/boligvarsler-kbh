"""CEJ – udlejning.cej.dk

Fund (live, Fase 1): Udlejningsportalen ``https://udlejning.cej.dk/find-bolig``
er en enkeltsides-app (SPA) der henter data fra et AWS API Gateway-endpoint
(``*.execute-api.eu-central-1.amazonaws.com``). Rå HTML indeholder derfor ingen
boliger. Siden svarede desuden 429 (Too Many Requests) ved gentagne kald –
altså aktiv rate-limiting/botbeskyttelse.

Status: IKKE aktiv endnu. For at færdiggøre den skal det nøjagtige API-kald
(sti + query-parametre) udtrækkes fra sidens JavaScript-bundle, og der skal
hentes meget skånsomt (få kald, god pause) pga. rate-limiting. Slå evt. 'cej'
fra i config.yaml indtil da. Scraperen returnerer en tom liste (fejler ikke).
"""

from __future__ import annotations

import logging

from boligagent.models import Listing
from .base import BaseScraper

log = logging.getLogger("boligagent.scraper.cej")


class CejScraper(BaseScraper):
    name = "cej"
    source = "CEJ"

    def fetch(self) -> list[Listing]:
        log.info("[cej] ikke aktiv endnu (SPA mod AWS-API + rate-limiting). "
                 "Udtræk API-kaldet fra JS-bundlen for at færdiggøre. Returnerer 0.")
        return []
