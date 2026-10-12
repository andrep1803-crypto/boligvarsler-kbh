"""City Apartment – https://www.cityapartment.dk

Datakilde (VERIFICERET live): WordPress med custom post type ``cityapartments``.
Liste via REST: ``/wp-json/wp/v2/cityapartments?per_page=100`` (titel = adresse,
+ link). m²/pris/postnr står IKKE i REST (ACF ikke eksponeret), så vi henter
hver detaljeside.

To faldgruber vi håndterer (bekræftet live):
  1) Siden afviser korte User-Agents med en 733-byte stub. Vi bruger en fuld
     Chrome-User-Agent (sat i ScrapeContext/config) – ellers kommer der ingen data.
  2) Detaljesiden viser både den aktuelle bolig OG en "featured" bolig med
     engelske felter ("Zip code 1620", "DKK/md."). Vi må IKKE bare tage første
     match. Derfor:
       * postnr læses som det 4-cifrede tal LIGE efter adressen i undertitlen
         ("Willemoesgade 51, kl. tv. 2100 Østerbro").
       * m²/værelser/husleje læses fra den mindste blok der indeholder både
         adressen og "specifications" (den danske hovedblok med
         "Månedlig leje 13.500,00 kr.").

P-pladser (titel indeholder "parkering") springes over – de er ikke boliger.
"""

from __future__ import annotations

import html as html_lib
import logging
import re
from typing import Optional

from boligagent.models import Listing
from .base import BaseScraper
from .parsing import clean_text

log = logging.getLogger("boligagent.scraper.cityapartment")

REST_URL = "https://www.cityapartment.dk/wp-json/wp/v2/cityapartments"


class CityApartmentScraper(BaseScraper):
    name = "cityapartment"
    source = "City Apartment"

    def fetch(self) -> list[Listing]:
        from selectolax.lexbor import LexborHTMLParser

        items = self.get_json(REST_URL, params={"per_page": "100"})
        if not isinstance(items, list):
            log.warning("[cityapartment] uventet REST-svar.")
            return []

        listings: list[Listing] = []
        for it in items:
            link = it.get("link")
            titel = clean_text(html_lib.unescape(_rendered(it.get("title")) or ""))
            if not link or not titel:
                continue
            if "parkering" in titel.lower():
                continue  # p-pladser er ikke boliger
            try:
                page = self.get(link).text
            except Exception as exc:
                log.warning("[cityapartment] kunne ikke hente %s: %s", link, exc)
                listings.append(Listing(kilde=self.source, url=link, titel=titel, adresse=titel))
                continue
            listings.append(self._parse_detail(LexborHTMLParser(page), link, titel))
        return listings

    def _parse_detail(self, tree, link: str, titel: str) -> Listing:
        h1 = tree.css_first("h1")
        addr = h1.text().strip() if h1 else titel

        body = re.sub(r"\s+", " ", (tree.body.text() if tree.body else ""))
        # postnr = 4-cifret lige efter adressen i undertitlen
        postnr = None
        if addr in body:
            m = re.search(r"\b(\d{4})\b", body.split(addr, 1)[-1][:40])
            if m:
                postnr = int(m.group(1))

        # Afgræns til den danske hovedblok (adresse + "specifications")
        block = self._specs_block(tree, addr)
        btx = re.sub(r"\s+", " ", block.text()) if block else body

        billede = None
        img = tree.css_first("main img") or tree.css_first("img")
        if img:
            billede = img.attributes.get("src") or img.attributes.get("data-src")

        # Specs-blokken angiver "Furnished"/"Unfurnished" (tjek Unfurnished først,
        # da den indeholder delstrengen "furnished").
        low = btx.lower()
        if "unfurnished" in low:
            moebleret: Optional[bool] = False
        elif "furnished" in low:
            moebleret = True
        else:
            moebleret = None

        return Listing(
            kilde=self.source,
            url=link,
            titel=addr,
            adresse=addr,
            postnr=postnr,
            m2=_num(btx, r"(\d+)\s*m²"),
            vaerelser=_vaerelser(btx),
            husleje=_husleje(btx, body),
            aconto=_num(btx, r"(?:Aconto|Forbrug|A/C\w*)\s*([\d.]+)")
            or _num(body, r"Heating\s*([\d.]+)\s*DKK"),
            depositum=_num(btx, r"Depositum\s*([\d.]+)")
            or _num(body, r"Deposit\s*([\d.]+)\s*DKK"),
            indflytning=_grab(btx, r"(?:Indflytning|Overtages|Ledig fra)\s*:?\s*([\w/.\- ]{4,20})"),
            billede_url=billede,
            moebleret=moebleret,
        )

    @staticmethod
    def _specs_block(tree, addr: str):
        best = None
        for n in tree.css("div,section,article"):
            tx = n.text() or ""
            if addr and addr in tx and "m²" in tx and "specifications" in tx.lower():
                if best is None or len(tx) < len(best[1]):
                    best = (n, tx)
        return best[0] if best else None


def _rendered(field) -> Optional[str]:
    if isinstance(field, dict):
        return field.get("rendered")
    return field if isinstance(field, str) else None


def _grab(text: str, pattern: str) -> Optional[str]:
    m = re.search(pattern, text)
    return clean_text(m.group(1)) if m else None


def _num(text: str, pattern: str) -> Optional[int]:
    m = re.search(pattern, text)
    if not m:
        return None
    digits = re.sub(r"[.\s]", "", m.group(1))
    try:
        return int(digits)
    except ValueError:
        return None


def _husleje(btx: str, body: str) -> Optional[int]:
    """Månedlig leje. Danske sider skriver "Månedlig leje X kr." i specs-blokken;
    engelske sider skriver kun "X DKK/md." i en prissektion udenfor blokken,
    sammen med varmen ("Heating Y DKK/md.").

    For de engelske: vælg det DKK/md-tal der passer bedst med depositum/3
    (depositum = 3 mdr. leje på denne side), ellers det største tal – varmen er
    altid et lille beløb og sorteres fra af nedre grænse.
    """
    v = _num(btx, r"Månedlig leje\s*([\d.]+)")
    if v:
        return v
    mds = [
        int(re.sub(r"[.\s]", "", m))
        for m in re.findall(r"([\d.]+)\s*DKK/md", body)
    ]
    mds = [m for m in mds if 1500 <= m <= 60000]  # frasortér varme/urealistisk
    if not mds:
        return None
    dep = _num(body, r"Deposit\s*([\d.]+)\s*DKK")
    if dep:
        target = dep / 3
        return min(mds, key=lambda m: abs(m - target))
    return max(mds)


def _vaerelser(text: str) -> Optional[int]:
    """Antal værelser på dansk (stue + soveværelser).

    City Apartments "N Rooms"-felt tæller kun opholdsstuer, så en 2-værelses
    står som "1 Rooms". Den rigtige værelsestælling står som "N-room apartment"
    (= Rooms + Bedrooms). Vi foretrækker den; ellers summerer vi Rooms+Bedrooms;
    ellers falder vi tilbage til Rooms alene.
    """
    m = re.search(r"(\d+)\s*-\s*room apartment", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    rooms = _num(text, r"(\d+)\s*Rooms")
    bedrooms = _num(text, r"(\d+)\s*Bedrooms")
    if rooms is not None and bedrooms is not None:
        return rooms + bedrooms
    return rooms
