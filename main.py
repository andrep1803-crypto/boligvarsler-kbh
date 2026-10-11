#!/usr/bin/env python3
"""Boligvarsler for København – entrypoint.

Brug:
    python main.py            # normal kørsel (henter, filtrerer, varsler)
    python main.py --test     # kører alle scrapere én gang og printer fund,
                              #   gemmer intet og sender INGEN varsler
    python main.py -v         # mere detaljeret logning (debug)
"""

from __future__ import annotations

import argparse
import logging
import sys

from boligagent.runner import run


def main() -> int:
    parser = argparse.ArgumentParser(description="Boligvarsler for København")
    parser.add_argument("--test", action="store_true",
                        help="Kør alle scrapere én gang, print fund, send ingen varsler.")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Detaljeret (debug) logning.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    return run(test_mode=args.test)


if __name__ == "__main__":
    sys.exit(main())
