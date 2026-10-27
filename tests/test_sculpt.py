"""sculpt.py：十二生肖兽首（雕塑式简化）。"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))

from generator import sculpt, western  # noqa: E402

ZODIAC = western.ZODIAC_SOUTH + western.ZODIAC_NORTH


class AnimalHeadTests(unittest.TestCase):
    def test_all_twelve_valid(self):
        for kind in ZODIAC:
            m, _mouth = sculpt.sculpted_head(kind)
            m.validate()

    def test_mouth_in_front(self):
        for kind in ZODIAC:
            m, mouth = sculpt.sculpted_head(kind)
            (_, _, _), (amax, _, _) = m.bounds()
            self.assertGreater(mouth[0], 5.0, kind)                 # 口在颈前方
            self.assertLessEqual(mouth[0], amax + 1.0, kind)          # 鼻孔压痕使吻端略后缩，喷口贴吻端

    def test_long_muzzles_longer(self):
        length = {k: sculpt.sculpted_head(k)[1][0] for k in ("horse", "monkey", "tiger", "rat")}
        self.assertGreater(length["horse"], length["monkey"])
        self.assertGreater(length["rat"], length["tiger"])

    def test_head_asset_loaded_and_mouth_in_front(self):
        import tempfile
        from pathlib import Path as P
        with tempfile.TemporaryDirectory() as d:
            P(d, "ox.obj").write_text("v 0 0 0\nv 10 0 10\nv 0 5 34\nv -5 -5 20\nf 1 2 3\nf 1 3 4\n", encoding="utf-8")
            m, mouth = sculpt.load_head_asset("ox", P(d))
            m.validate()
            self.assertEqual(mouth, (10.0, 0.0, 10.0))
            self.assertIsNone(sculpt.load_head_asset("pig", P(d)))

    def test_figure_assets_loaded_with_snout(self):
        import tempfile
        from pathlib import Path as P
        with tempfile.TemporaryDirectory() as d:
            P(d, "a.obj").write_text("v 0 0 0\nv 0.3 0 0.8\nv -0.1 0.2 1.0\nv 0 -0.2 0.5\nf 1 2 3\nf 1 3 4\n",
                                     encoding="utf-8")
            figs = sculpt.load_figure_assets(P(d))
            self.assertEqual(len(figs), 1)
            figs[0][0].validate()
            self.assertEqual(figs[0][1], (0.3, 0.0, 0.8))             # 吻端：头部高度带内最靠前

    def test_place_faces_direction(self):
        m, mouth = sculpt.sculpted_head("ox")
        p = sculpt.place_point(mouth, 100.0, 0.0, 0.0, (0.0, -1.0), 2.0)
        self.assertAlmostEqual(p[0], 100.0, delta=1e-6)
        self.assertLess(p[1], 0.0)                                  # 朝 −Y


if __name__ == "__main__":
    unittest.main()
