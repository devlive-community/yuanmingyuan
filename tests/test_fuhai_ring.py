"""test_fuhai_ring.py — 福海环湖四景单测（澡身浴德/平湖秋月/接秀山房/涵虚朗鉴）。"""

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "blender"))

from generator import config, roof, plan, scene  # noqa: E402

OSM_GARDEN = _ROOT / "data" / "gardens" / "sanyuan_osm.yaml"


class FuhaiRingTests(unittest.TestCase):
    def setUp(self):
        self.garden = config.load_garden(OSM_GARDEN)
        self.parts = dict(scene.build_garden(self.garden, OSM_GARDEN))
        self.fuhai = self.parts["water_18108375_210654679/water"]
        (self.fx0, self.fy0, _), (self.fx1, self.fy1, _) = self.fuhai.bounds()

    def test_twelve_scenes(self):
        self.assertGreaterEqual(len(self.garden.scenes), 21)

    def test_zaoshen_on_west_shore(self):
        (x0, _, _), (x1, _, _) = self.parts["zaoshen_yude/zaoshen_chengxuxie/platform"].bounds()
        self.assertLess(x1, self.fx0)  # 整体在福海西岸之外（陆地）

    def test_pinghu_on_north_shore(self):
        (_, y0, _), (_, _, _) = self.parts["pinghu_qiuyue/pinghu_zhengdian/platform"].bounds()
        self.assertGreater(y0, self.fy1)  # 整体在福海北岸之外（陆地）

    def test_jiexiu_and_hanxu_on_east_shore(self):
        for label in ("jiexiu_shanfang/jiexiu_zhengdian/platform", "hanxu_langjian/hanxu_leifeng/platform"):
            (x0, _, _), (_, _, _) = self.parts[label].bounds()
            self.assertGreater(x0, self.fx1)  # 整体在福海东岸之外（陆地）

    def test_shuangfeng_double_eave(self):
        # 双峰插云亭（重檐四方亭）：屋顶含腰檐环带
        pt = config.load_building(_ROOT / "data" / "buildings" / "pinghu_shuangfeng.yaml")
        pl = plan.build_plan(pt)
        z_base = pt.platform_height_cm + 2 * 480.0
        plain = roof.build_roof_xieshan(pl, z_base, style="卷棚歇山")
        fancy = roof.build_roof_xieshan(pl, z_base, style="卷棚歇山",
                                        skirts=(pt.platform_height_cm + 480.0,))
        self.assertEqual(len(fancy.vertices), len(plain.vertices) + 8)


if __name__ == "__main__":
    unittest.main()
