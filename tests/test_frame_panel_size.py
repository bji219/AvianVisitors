"""display.py must compose at the attached panel's size, not the 13.3"'s.

PANEL_W/PANEL_H used to be hardcoded to the 13.3" panel (1200x1600 portrait).
push_panel() rescales whatever it is handed to the detected device, so a 7.3"
Impression (800x480 landscape) did not fail -- it silently squashed, because
1600x1200 -> 800x480 scales x by 0.5 and y by 0.4. Birds came out 26% wider
than tall.
"""

import importlib.util
import pathlib
import unittest

from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parents[1]
FRAME = ROOT / "frame"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PanelSizeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.display = load_module("frame_display", FRAME / "display.py")

    def test_default_is_the_7_3_inch_frame(self):
        """This fork drives a 7.3" Inky Frame; the 13.3" is opt-in by name."""
        self.assertEqual(self.display.resolve_panel_size({}), (480, 800))
        self.assertEqual((self.display.PANEL_W, self.display.PANEL_H), (480, 800))
        self.assertEqual(self.display.DEFAULTS["opening"], 1.0)
        self.assertEqual(
            self.display.resolve_panel_size({"panel": "el133uf1"}), (1200, 1600)
        )

    def test_panel_name_selects_geometry(self):
        self.assertEqual(self.display.resolve_panel_size({"panel": "7.3"}), (480, 800))
        self.assertEqual(self.display.resolve_panel_size({"panel": "13.3"}), (1200, 1600))
        self.assertEqual(self.display.resolve_panel_size({"panel": " 7.3 "}), (480, 800))

    def test_explicit_dimensions_win(self):
        self.assertEqual(
            self.display.resolve_panel_size({"panel": "7.3", "panel_w": 600, "panel_h": 900}),
            (600, 900),
        )

    def test_unknown_panel_falls_back_rather_than_raising(self):
        self.assertEqual(self.display.resolve_panel_size({"panel": "nonesuch"}), (480, 800))
        self.assertEqual(self.display.resolve_panel_size({"panel_w": 0, "panel_h": 0}), (480, 800))

    def test_opening_never_overflows_the_panel_width(self):
        """The opening is a 1:sqrt(2) box scaled off panel height. On a 3:5
        panel its width would pass the edge above 0.848, so it is capped there,
        and opening = 1 is the whole screen."""
        self.display.PANEL_W, self.display.PANEL_H = 480, 800
        try:
            w, h = self.display.opening_size(0.84)
            self.assertAlmostEqual(w, 0.84 * 800 / 1.41421, places=3)
            self.assertEqual(self.display.opening_size(1.0), (480, 800))
            self.assertEqual(self.display.opening_size(0.9)[0], 480)
        finally:
            self.display.PANEL_W, self.display.PANEL_H = 480, 800

    def test_opening_on_the_13_3_inch_keeps_its_a5_shape(self):
        self.display.PANEL_W, self.display.PANEL_H = 1200, 1600
        try:
            w, h = self.display.opening_size(0.7071)
            self.assertAlmostEqual(w / h, 1 / 1.41421, places=4)
        finally:
            self.display.PANEL_W, self.display.PANEL_H = 480, 800

    def test_full_opening_places_content_edge_to_edge(self):
        self.display.PANEL_W, self.display.PANEL_H = 480, 800
        try:
            placed = self.display._place(Image.new("RGB", (480, 800), (0, 0, 0)),
                                         (255, 255, 255), 0.0, 1.0)
            self.assertEqual(placed.size, (480, 800))
            self.assertEqual(placed.getcolors(), [(480 * 800, (0, 0, 0))])
        finally:
            self.display.PANEL_W, self.display.PANEL_H = 480, 800

    def test_composing_at_panel_size_needs_no_rescale(self):
        """push_panel() only resizes when the rotated buffer misses the device.
        Composing at the panel's own size avoids that resize entirely."""
        for (pw, ph), dev in (((480, 800), (800, 480)), ((1200, 1600), (1600, 1200))):
            with self.subTest(panel=(pw, ph)):
                self.assertEqual(Image.new("RGB", (pw, ph)).rotate(90, expand=True).size, dev)

    def test_circle_stays_round_at_panel_size_and_squashes_at_13_3(self):
        def bbox_ratio(size, dev=(800, 480)):
            w, h = size
            img = Image.new("L", size, 0)
            r = min(w, h) // 4
            ImageDraw.Draw(img).ellipse(
                (w // 2 - r, h // 2 - r, w // 2 + r, h // 2 + r), fill=255
            )
            buf = img.rotate(90, expand=True)
            if buf.size != dev:
                buf = buf.resize(dev, Image.LANCZOS)
            x0, y0, x1, y1 = buf.point(lambda v: 255 if v > 127 else 0).getbbox()
            return (x1 - x0) / (y1 - y0)

        self.assertAlmostEqual(bbox_ratio((480, 800)), 1.0, delta=0.02)
        self.assertGreater(bbox_ratio((1200, 1600)), 1.2)


if __name__ == "__main__":
    unittest.main()
