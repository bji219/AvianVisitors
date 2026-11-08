"""Cap the frame collage's species, keeping one slot for a rare visitor.

Kept free of third-party imports so it can be tested without Playwright,
which shoot.py imports at load time.

`species` are the site's recent-API rows (sci, com, n, best_conf, last_seen).
`rarity` maps a scientific name to the number of distinct days the station
heard it in its lookback (fewest = rarest); a name missing from it counts as
0 days.
"""
from __future__ import annotations


def _num(row: dict, key: str) -> float:
    return row.get(key) or 0


def cap_species(species: list[dict], max_n: int, rarity: dict[str, int],
                min_n: int = 2, min_conf: float = 0.8) -> tuple[list[dict], dict | None]:
    """Keep the max_n - 1 most-heard species plus the rarest eligible one.

    A rare candidate needs at least `min_n` detections in the window or a top
    confidence of at least `min_conf`: BirdNET's rare calls are
    disproportionately false IDs. With no eligible candidate the slot goes to
    the next most-heard. Returns (kept, rare_pick) with `kept` in the input
    order; max_n <= 0, or no more species than max_n, returns the input.
    """
    if max_n <= 0 or len(species) <= max_n:
        return species, None

    # Most heard first; a tie on n goes to the more recently heard.
    by_heard = sorted(range(len(species)), reverse=True,
                      key=lambda i: (_num(species[i], "n"), species[i].get("last_seen") or ""))
    keep = set(by_heard[:max_n - 1])
    rest = by_heard[max_n - 1:]

    eligible = [i for i in rest
                if _num(species[i], "n") >= min_n or _num(species[i], "best_conf") >= min_conf]
    rare = None
    if eligible:
        # Stable sorts, least significant key first: later last_seen, then
        # higher confidence, then fewest days heard.
        eligible.sort(key=lambda i: species[i].get("last_seen") or "", reverse=True)
        eligible.sort(key=lambda i: _num(species[i], "best_conf"), reverse=True)
        eligible.sort(key=lambda i: rarity.get(species[i].get("sci"), 0))
        pick = eligible[0]
        rare = species[pick]
    else:
        pick = rest[0]

    keep.add(pick)
    return [species[i] for i in sorted(keep)], rare
