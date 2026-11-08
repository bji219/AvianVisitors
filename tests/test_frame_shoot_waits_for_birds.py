"""shoot.py must wait for the bird list before it captures.

The page shows its empty state ("listening for birds…") while the recent
list is still loading. shoot.py used to wait for "a tile or the empty state",
so a station whose recent query takes a couple of seconds -- PowellCt, with a
quarter of a million detections -- was captured as an empty nest every time.
"""

import http.server
import importlib.util
import json
import pathlib
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[1]
FRAME = ROOT / "frame"
FRONTEND = ROOT / "avian" / "frontend"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BIRDS = [{"sci": "Sitta carolinensis", "com": "White-breasted Nuthatch", "n": 23, "best_conf": 0.9,
          "last_seen": "2026-11-07 15:46:32"},
         {"sci": "Corvus brachyrhynchos", "com": "American Crow", "n": 52, "best_conf": 0.95,
          "last_seen": "2026-11-07 16:10:00"},
         {"sci": "Haemorhous mexicanus", "com": "House Finch", "n": 50, "best_conf": 0.93,
          "last_seen": "2026-11-07 16:00:00"}]


class SlowSite(http.server.SimpleHTTPRequestHandler):
    """The bundled frontend, with a bird list that takes RECENT_DELAY_S."""
    species = []
    RECENT_DELAY_S = 2.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND), **kwargs)

    def log_message(self, *args):
        pass

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path)
        if path.path.endswith("birdnet-api.php"):
            query = urllib.parse.parse_qs(path.query)
            body = {}
            if query.get("action") == ["recent"]:
                time.sleep(self.RECENT_DELAY_S)
                body = {"hours": 12, "species": SlowSite.species, "as_of": ""}
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        super().do_GET()


class ShootWaitsForBirdsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # test_frame_birdweather leaves stand-in playwright modules in
        # sys.modules (no __file__); this test needs the real browser.
        cls.stubs = {name: sys.modules.pop(name) for name in ("playwright", "playwright.sync_api")
                     if name in sys.modules and getattr(sys.modules[name], "__file__", None) is None}
        try:
            cls.shoot = load_module("frame_shoot_real", FRAME / "shoot.py")
        except ImportError:
            sys.modules.update(cls.stubs)
            raise unittest.SkipTest("playwright not installed")
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), SlowSite)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}/"
        cls.tmp = pathlib.Path(tempfile.mkdtemp())

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        sys.modules.update(cls.stubs)

    def render(self, species, name):
        SlowSite.species = species
        out = self.tmp / name
        try:
            self.shoot.shoot(self.url, str(out), vw=240, vh=400, dsf=1, timeout_ms=8000)
        except Exception as e:  # no browser installed for this Playwright
            if "Executable doesn't exist" in str(e):
                self.skipTest("no Playwright browser")
            raise
        return out.read_bytes()

    def test_a_slow_bird_list_is_drawn_not_the_empty_state(self):
        with_birds = self.render(BIRDS, "birds.png")
        empty = self.render([], "empty.png")
        self.assertNotEqual(with_birds, empty)


if __name__ == "__main__":
    unittest.main()
