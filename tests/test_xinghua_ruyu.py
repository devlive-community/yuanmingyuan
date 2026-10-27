"""test_xinghua_ruyu.py — 杏花春馆 / 茹古涵今单测。"""

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "blender"))

from generator import config, scene  # noqa: E402

OSM_GARDEN = _ROOT / "data" / "gardens" / "sanyuan_osm.yaml"


class XinghuaRuyuTests(unittest.TestCase):
    def setUp(self):
        self.garden = config.load_garden(OSM_GARDEN)
        self.parts = dict(scene.build_garden(self.garden, OSM_GARDEN))

    def test_scene_counts_grow_only(self):
        # 总园景数只增不减（当前 21：19 + 杏花春馆 + 茹古涵今）
        self.assertGreaterEqual(len(self.garden.scenes), 21)

    def test_xinghua_composition(self):
        for k in ("xinghua_chunyu_xuan/platform", "xinghua_gongmen/platform", "xingde_nanshan_ting/platform", "cuiwei_tang/platform"):
            self.assertIn(f"xinghua_chunjuan/{k}", self.parts)
        # 宫门在南，主殿居中
        (_, gy0, _), (_, gy1, _) = self.parts["xinghua_chunjuan/xinghua_gongmen/platform"].bounds()
        (_, dy0, _), (_, _, _) = self.parts["xinghua_chunjuan/xinghua_chunyu_xuan/platform"].bounds()
        self.assertLess(gy1, dy0)

    def test_ruyu_composition(self):
        for k in ("ruyu_zhengdian/platform", "ruyu_shaojing_xuan/platform", "ruyu_maoyu_zhai/platform", "ruyu_zhuxiang_zhai/platform"):
            self.assertIn(f"ruyu_hangjin/{k}", self.parts)
        # 韶景轩在正殿之北
        (_, sy0, _), (_, _, _) = self.parts["ruyu_hangjin/ruyu_shaojing_xuan/platform"].bounds()
        (_, _, dy1) = self.parts["ruyu_hangjin/ruyu_zhengdian/platform"].bounds()[1]
        self.assertGreater(sy0, dy1)
        # 正殿五楹：181D + 42D = 223D × 8 = 1784（总园 rot 90° 后面阔沿 Y）
        (_, y0, _), (_, y1, _) = self.parts["ruyu_hangjin/ruyu_zhengdian/platform"].bounds()
        self.assertAlmostEqual(y1 - y0, 1784.0, places=4)
        (x0, _, _), (x1, _, _) = self.parts["ruyu_hangjin/ruyu_zhengdian/platform"].bounds()
        self.assertAlmostEqual(x1 - x0, (68 + 42) * 8.0, places=4)


if __name__ == "__main__":
    unittest.main()
