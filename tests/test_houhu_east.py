"""test_houhu_east.py — 镂月开云 / 天然图画单测（后湖东岸）。"""

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "blender"))

from generator import config, scene  # noqa: E402

OSM_GARDEN = _ROOT / "data" / "gardens" / "sanyuan_osm.yaml"


class HouhuEastTests(unittest.TestCase):
    def setUp(self):
        self.garden = config.load_garden(OSM_GARDEN)
        self.parts = dict(scene.build_garden(self.garden, OSM_GARDEN))
        (self.fx0, self.fy0, _), (self.fx1, self.fy1, _) = self.parts["water_40724042/water"].bounds()

    def test_scenes_grow(self):
        self.assertGreaterEqual(len(self.garden.scenes), 23)

    def test_louyue_composition_on_southeast_shore(self):
        for k in ("louyue_zhengdian/platform", "louyue_yulanfen/platform"):
            self.assertIn(f"louyue_kaiyun/{k}", self.parts)
        (x0, _, _), (x1, _, _) = self.parts["louyue_kaiyun/louyue_zhengdian/platform"].bounds()
        self.assertGreater(x0, self.fx1)          # 后湖东界之外（东南岸）
        (_, y0, _), (_, y1, _) = self.parts["louyue_kaiyun/louyue_zhengdian/platform"].bounds()
        self.assertGreater(y0, (self.fy0 + self.fy1) / 2)  # 偏南半

    def test_tianran_composition_on_east_shore(self):
        for k in ("tianran_fanglou/platform", "tianran_lanyin_ge/platform", "tianran_zhukao_lou/platform", "tianran_wufu_tang/platform"):
            self.assertIn(f"tianran_tuhua/{k}", self.parts)
        # 朗吟阁与竹薖楼临湖（在南），五福堂在北
        (_, ly1, _), (_, _, _) = self.parts["tianran_tuhua/tianran_lanyin_ge/platform"].bounds()
        (_, _, _), (_, wy0, _) = self.parts["tianran_tuhua/tianran_wufu_tang/platform"].bounds()
        self.assertLess(ly1, wy0)
        # 临湖两楼均为二层：柱顶 = 台基 64 + 2×480
        (_, _, _, ), (_, _, lz1) = self.parts["tianran_tuhua/tianran_lanyin_ge/columns"].bounds()
        self.assertAlmostEqual(lz1, 64.0 + 2 * 480.0, places=4)


if __name__ == "__main__":
    unittest.main()
