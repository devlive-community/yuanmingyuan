"""test_fuhai_south.py — 福海南岸收口单测（夹镜鸣琴桥亭 / 别有洞天）。"""

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "blender"))

from generator import config, scene  # noqa: E402

OSM_GARDEN = _ROOT / "data" / "gardens" / "sanyuan_osm.yaml"


class FuhaiSouthTests(unittest.TestCase):
    def setUp(self):
        self.garden = config.load_garden(OSM_GARDEN)
        self.parts = dict(scene.build_garden(self.garden, OSM_GARDEN))
        self.fuhai = self.parts["water_18108375_210654679/water"]
        (self.fx0, self.fy0, _), (self.fx1, self.fy1, _) = self.fuhai.bounds()

    def test_fifteen_scenes(self):
        self.assertGreaterEqual(len(self.garden.scenes), 21)

    def test_jiajing_bridge_parts(self):
        labels = ["abutment_west", "abutment_east", "deck", "pavilion/platform", "pavilion/columns", "pavilion/roof"]
        for k in labels:
            self.assertIn(f"jiajing_mingqin/{k}", self.parts)
        # 桥面在 0..120，桥亭坐于其上
        (_, _, d0), (_, _, d1) = self.parts["jiajing_mingqin/deck"].bounds()
        self.assertAlmostEqual(d0, 0.0)
        self.assertAlmostEqual(d1, 120.0)
        (_, _, t0), (_, _, _) = self.parts["jiajing_mingqin/pavilion/columns"].bounds()
        self.assertAlmostEqual(t0, 120.0 + 19.2)  # 桥面 + 台基 0.6 尺

    def test_biedong_composition(self):
        for k in ("biedong_shishang_zhai/platform", "biedong_nacui_lou/platform", "biedong_shuimu_ge/platform"):
            self.assertIn(f"biedong_tiantian/{k}", self.parts)
        (_, _, _), (_, _, nl1) = self.parts["biedong_tiantian/biedong_nacui_lou/platform"].bounds()
        (_, _, _), (_, _, zhai1) = self.parts["biedong_tiantian/biedong_shishang_zhai/platform"].bounds()
        self.assertEqual(nl1, zhai1)  # 同一台基高

    def test_shores_outside_fuhai(self):
        (_, jy0, _), (_, jy1, _) = self.parts["jiajing_mingqin/deck"].bounds()
        self.assertLess(jy1, self.fy0)  # 桥亭在福海南岸之外（陆地）
        (bx0, _, _), (_, _, _) = self.parts["biedong_tiantian/biedong_shishang_zhai/platform"].bounds()
        self.assertGreater(bx0, self.fx1)  # 别有洞天在福海东界之外（东南隅）


if __name__ == "__main__":
    unittest.main()
