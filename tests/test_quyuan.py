"""test_quyuan.py — 曲院风荷单测：五间正殿 + 九孔桥（八墩）+ 金鳌/玉蝀牌楼。"""

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "blender"))

from generator import bridges, config, scene  # noqa: E402

OSM_GARDEN = _ROOT / "data" / "gardens" / "sanyuan_osm.yaml"
QUYUAN_SCENE = _ROOT / "data" / "scenes" / "quyuan_fenghe.yaml"


class QuyuanSceneTests(unittest.TestCase):
    def setUp(self):
        self.sc = config.load_scene(QUYUAN_SCENE)
        self.parts = dict(scene.build_scene(self.sc, QUYUAN_SCENE))

    def test_composition(self):
        roles = [k for k in self.parts]
        for k in ("main_hall/platform", "main_hall/columns", "main_hall/roof", "nine_arch_bridge/deck", "paifang_jinao", "paifang_yudong"):
            self.assertIn(k, roles)
        piers = [k for k in roles if k.startswith("nine_arch_bridge/pier_")]
        self.assertEqual(len(piers), 8)  # 九孔 → 八墩
        self.assertEqual(len(self.parts), 14)  # 3 + 1 + 8 + 2

    def test_bridge_heights(self):
        (_, _, d0), (_, _, d1) = self.parts["nine_arch_bridge/deck"].bounds()
        self.assertAlmostEqual(d0, 120.0)
        self.assertAlmostEqual(d1, 120.0 + bridges.NINE_DECK_T_CM)
        (_, _, p0), (_, _, p1) = self.parts["nine_arch_bridge/pier_1"].bounds()
        self.assertAlmostEqual(p0, 0.0)   # 墩自水底地面起
        self.assertAlmostEqual(p1, 120.0)

    def test_zhengdian_five_bays(self):
        (x0, _, _), (x1, _, _) = self.parts["main_hall/platform"].bounds()
        # 五间 181D ＋ 上檐出 42D ＝ 223D × 8 cm = 1784
        self.assertAlmostEqual(x1 - x0, 1784.0, places=4)


class QuyuanGardenTests(unittest.TestCase):
    def test_in_garden(self):
        g = config.load_garden(OSM_GARDEN)
        self.assertGreaterEqual(len(g.scenes), 21)
        parts = dict(scene.build_garden(g, OSM_GARDEN))
        self.assertIn("quyuan_fenghe/nine_arch_bridge/deck", parts)
        # 曲院风荷在福海西界之外（西岸）
        (fx0, _, _), (_, _, _) = parts["water_18108375_210654679/water"].bounds()
        (bx0, _, _), (_, _, _) = parts["quyuan_fenghe/main_hall/platform"].bounds()
        self.assertLess(bx0, fx0)


if __name__ == "__main__":
    unittest.main()
