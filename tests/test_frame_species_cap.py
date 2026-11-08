"""The frame collage's species cap, with one slot kept for a rare visitor.

A busy station (PowellCt) hears far more species than a 7.3" collage can
draw legibly. cap_species keeps the most-heard birds plus the rarest recent
visitor -- rare for that yard, by how few days it was heard in the last
month -- while guarding the rare slot against BirdNET's one-off false IDs.
"""

import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
FRAME = ROOT / "frame"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cap = load_module("species_cap", FRAME / "species_cap.py").cap_species


def sp(sci, n, conf=0.9, last="2026-11-07 08:00"):
    return {"sci": sci, "com": sci.upper(), "n": n, "best_conf": conf, "last_seen": last}


class SpeciesCapTests(unittest.TestCase):
    def test_under_the_cap_is_unchanged(self):
        birds = [sp("a", 5), sp("b", 1)]
        self.assertEqual(cap(birds, 8, {}), (birds, None))

    def test_cap_of_zero_means_off(self):
        birds = [sp(str(i), i + 1) for i in range(12)]
        self.assertEqual(cap(birds, 0, {})[0], birds)

    def test_keeps_most_heard_plus_the_rarest(self):
        birds = [sp(f"s{i}", 20 - i) for i in range(10)]            # s0 most heard
        rarity = {f"s{i}": 30 for i in range(10)} | {"s8": 2, "s9": 1}
        kept, rare = cap(birds, 4, rarity)
        self.assertEqual({b["sci"] for b in kept}, {"s0", "s1", "s2", "s9"})
        self.assertEqual(rare["sci"], "s9")

    def test_output_keeps_the_api_order(self):
        birds = [sp("x", 1, 0.9), sp("top", 50), sp("y", 30), sp("z", 2)]
        kept, rare = cap(birds, 3, {"x": 1, "top": 30, "y": 30, "z": 30})
        self.assertEqual(([b["sci"] for b in kept], rare["sci"]), (["x", "top", "y"], "x"))

    def test_rare_slot_needs_two_detections_or_high_confidence(self):
        birds = [sp(f"s{i}", 20 - i) for i in range(8)] + [sp("lone", 1, 0.7)]
        rarity = {f"s{i}": 30 for i in range(8)} | {"s7": 3, "lone": 1}
        self.assertEqual(cap(birds, 4, rarity)[1]["sci"], "s7")
        birds[-1] = sp("lone", 1, 0.85)
        self.assertEqual(cap(birds, 4, rarity)[1]["sci"], "lone")

    def test_no_eligible_rare_fills_with_next_most_heard(self):
        birds = [sp("a", 9), sp("b", 8), sp("c", 7), sp("e", 1, 0.5),
                 sp("d", 1, 0.5, "2026-11-07 09:00")]
        kept, rare = cap(birds, 4, {"d": 1, "e": 1})
        self.assertIsNone(rare)
        self.assertEqual({b["sci"] for b in kept}, {"a", "b", "c", "d"})

    def test_rare_tie_breaks_on_confidence_then_recency(self):
        birds = [sp("a", 9), sp("b", 8), sp("p", 2, 0.81, "2026-11-07 07:00"),
                 sp("q", 2, 0.95, "2026-11-07 06:00"), sp("r", 2, 0.95, "2026-11-07 09:00")]
        self.assertEqual(cap(birds, 3, {"p": 1, "q": 1, "r": 1})[1]["sci"], "r")


class ApiHandlerTests(unittest.TestCase):
    """shoot.py applies the cap where it rewrites the site's recent list."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.shoot = load_module("shoot", FRAME / "shoot.py")
        except ImportError:
            raise unittest.SkipTest("playwright not installed")

    def test_api_handler_caps_the_recent_list(self):
        birds = [sp(f"s{i}", 20 - i) for i in range(10)]
        rarity = {f"s{i}": 30 for i in range(10)} | {"s9": 1}
        handler = self.shoot._make_api_handler(0, 12, None, species=birds,
                                               max_species=4, rarity=rarity)
        sent = {}

        class Route:  # only what the handler touches
            class request:
                url = "http://x/birdnet-api.php?action=recent&hours=12"

            def fulfill(self, **kw):
                sent.update(kw)

        handler(Route())
        names = [b["sci"] for b in json.loads(sent["body"])["species"]]
        self.assertEqual(names, ["s0", "s1", "s2", "s9"])


if __name__ == "__main__":
    unittest.main()
