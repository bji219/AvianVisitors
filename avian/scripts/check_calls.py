#!/usr/bin/env python3
"""Check avian/frontend/calls.json, the species-card call mnemonics.

Every phrase must come from a reputable published source and appear there
word for word; none are invented. Offline (the default, run by the tests):
structure, binomial names, approved source domains. --online also re-fetches
each source page and confirms every phrase is still printed on it.
"""

from __future__ import annotations

import argparse
import html
import json
import pathlib
import re
import sys
import time
import urllib.request

CALLS = pathlib.Path(__file__).resolve().parents[1] / "frontend" / "calls.json"
ALLOWED = ("https://www.audubon.org/field-guide/bird/",
           "https://www.allaboutbirds.org/guide/",
           "https://ebird.org/species/")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"


def problems(data: dict) -> list[str]:
    out = []
    for sci, entry in data.items():
        if not re.fullmatch(r"[A-Z][a-z]+ [a-z]+(?: [a-z]+)?", sci):
            out.append(f"{sci}: not a binomial name")
        phrases = entry.get("mnemonics")
        if not isinstance(phrases, list) or not phrases or not all(
                isinstance(p, str) and p.strip() and len(p) <= 80 for p in phrases):
            out.append(f"{sci}: mnemonics must be 1+ short non-empty strings")
        if not str(entry.get("url", "")).startswith(ALLOWED):
            out.append(f"{sci}: source URL not on an approved site")
        if not entry.get("source") or not entry.get("common"):
            out.append(f"{sci}: needs 'source' and 'common'")
    return out


def online(data: dict) -> list[str]:
    out = []
    for sci, entry in data.items():
        req = urllib.request.Request(entry["url"], headers={"User-Agent": UA})
        try:
            page = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
        except Exception as exc:                                  # noqa: BLE001
            out.append(f"{sci}: couldn't fetch {entry['url']} ({exc})")
            continue
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", page)))
        out += [f"{sci}: '{p}' no longer on {entry['url']}" for p in entry["mnemonics"] if p not in text]
        time.sleep(1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--online", action="store_true", help="re-verify every phrase against its source")
    args = ap.parse_args()
    data = json.loads(CALLS.read_text(encoding="utf-8"))
    found = problems(data) + (online(data) if args.online else [])
    for line in found:
        print(line, file=sys.stderr)
    print(f"{len(data)} species, {'problems: %d' % len(found) if found else 'ok'}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
