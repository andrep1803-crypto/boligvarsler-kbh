"""Lagring af hvilke annoncer der allerede er set, så du ikke får dubletter.

Valg af løsning
---------------
Vi gemmer en lille JSON-fil (``data/seen.json``) som committes tilbage til
repoet efter hver kørsel i GitHub Actions. Hvorfor dette frem for Actions-cache?

* Cachen kan blive smidt ud (den ryddes efter 7 dages inaktivitet og har en
  størrelsesgrænse), og en tabt cache ville give dig 50 varsler på én gang igen.
* En committet fil er 100 % holdbar, kan læses i git-historikken, og du kan
  se/redigere den manuelt hvis noget går galt.
* Filen er bitte lille (én linje pr. bolig), så støj i historikken er minimal.

Workflowet committer kun filen hvis den har ændret sig.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SEEN_PATH = DATA_DIR / "seen.json"
FAILS_PATH = DATA_DIR / "failures.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SeenStore:
    """Holder styr på allerede sete annonce-id'er."""

    def __init__(self, path: Path = SEEN_PATH):
        self.path = path
        self._seen: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._seen = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._seen = {}
        else:
            self._seen = {}

    @property
    def is_first_run(self) -> bool:
        """True hvis vi aldrig har gemt noget før (ingen fil / tom)."""
        return not self.path.exists() or len(self._seen) == 0

    def has(self, listing_id: str) -> bool:
        return listing_id in self._seen

    def add(self, listing_id: str) -> None:
        self._seen.setdefault(listing_id, _now_iso())

    def add_many(self, listing_ids: Iterable[str]) -> None:
        for lid in listing_ids:
            self.add(lid)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._seen, ensure_ascii=False, indent=0, sort_keys=True),
            encoding="utf-8",
        )

    def __len__(self) -> int:
        return len(self._seen)


class FailureStore:
    """Tæller fortløbende fejl pr. scraper, så vi kan advare efter N i træk."""

    def __init__(self, path: Path = FAILS_PATH):
        self.path = path
        self._counts: dict[str, int] = {}
        if self.path.exists():
            try:
                self._counts = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._counts = {}

    def record_success(self, scraper: str) -> None:
        self._counts[scraper] = 0

    def record_failure(self, scraper: str) -> int:
        """Øger tælleren og returnerer nyt antal fejl i træk."""
        self._counts[scraper] = self._counts.get(scraper, 0) + 1
        return self._counts[scraper]

    def count(self, scraper: str) -> int:
        return self._counts.get(scraper, 0)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._counts, ensure_ascii=False, indent=0, sort_keys=True),
            encoding="utf-8",
        )
