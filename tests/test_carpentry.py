"""carpentry.py：檐枋、墙体与门窗装修（S-042）。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))

from generator import carpentry, config, plan, units  # noqa: E402


def _params(**kw) -> config.BuildingParams:
    base = dict(id="t", name="t", doukou_cun=2.5, bays=5, depth_bays=3, bay_brackets=4, depth_brackets=3)
    base.update(kw)
    return config.BuildingParams(**base)


class EnclosureTests(unittest.TestCase):
    def build(self, **kw):
        p = _params(**kw)
        pl = plan.build_plan(p)
        return pl, dict(carpentry.build_enclosure(pl, p.platform_height_cm, p.stories,
                                                  enclosure=p.enclosure, corridor=p.corridor))

    def test_open_has_only_beams(self):
        _pl, parts = self.build(enclosure="open")
        self.assertEqual(list(parts), ["beams"])

    def test_front_has_all_components(self):
        _pl, parts = self.build()
        self.assertEqual(list(parts), list(carpentry.COMPONENTS))
        for m in parts.values():
            m.validate()

    def test_surround_has_no_solid_wall(self):
        _pl, parts = self.build(enclosure="surround")
        self.assertNotIn("red_wall", parts)
        self.assertIn("paper", parts)

    def test_beams_under_column_top(self):
        pl, parts = self.build(enclosure="open")
        (_, _, z0), (_, _, z1) = parts["beams"].bounds()
        top = _params().platform_height_cm + pl.column_height_cm
        self.assertAlmostEqual(z1, top)
        self.assertAlmostEqual(z0, top - units.BEAM_HEIGHT_PER_DIAMETER * pl.eave_column_diameter_cm)

    def test_walls_on_eave_line(self):
        pl, parts = self.build()
        (x0, y0, _), (x1, y1, _) = parts["red_wall"].bounds()
        half = units.WALL_THICK_PER_DIAMETER * pl.eave_column_diameter_cm / 2.0
        self.assertAlmostEqual(x1, pl.length / 2.0 + half)
        self.assertAlmostEqual(y1, pl.width / 2.0 + half)
        self.assertAlmostEqual(y0, -pl.width / 2.0)          # 两山墙跨满进深（柱中—柱中）

    def test_front_joinery_on_front_only(self):
        pl, parts = self.build()
        (_, y0, _), (_, y1, _) = parts["paper"].bounds()
        self.assertLess(y1, -pl.width / 2.0 + 10.0)           # 窗纸全在前檐

    def test_corridor_moves_enclosure_inward(self):
        pl, parts = self.build(corridor="surround")
        (_, y0, _), _ = parts["joinery"].bounds()
        self.assertGreater(y0, pl.y_lines[1] - 30.0)
        (_, by0, _), _ = parts["beams"].bounds()
        self.assertLess(by0, -pl.width / 2.0)                 # 外圈檐枋仍在

    def test_two_stories_fill_both(self):
        pl, parts = self.build(stories=2)
        (_, _, z0), (_, _, z1) = parts["paper"].bounds()
        base = _params().platform_height_cm
        self.assertLess(z0, base + pl.column_height_cm)
        self.assertGreater(z1, base + pl.column_height_cm)

    def test_leaf_count_even(self):
        for w in (150.0, 300.0, 440.0, 600.0):
            n = carpentry._leaf_count(w)
            self.assertEqual(n % 2, 0)
            self.assertLessEqual(w / n, carpentry.LEAF_MAX_CM)

    def test_invalid_values_rejected(self):
        with self.assertRaises(ValueError):
            _params(enclosure="glass").validate()
        with self.assertRaises(ValueError):
            _params(corridor="surround", depth_bays=2).validate()


if __name__ == "__main__":
    unittest.main()
