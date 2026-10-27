"""test_jiuzhou_north.py — 后湖三景单测（慈云普护/坦坦荡荡/上下天光）。"""

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "blender"))

from generator import config, scene  # noqa: E402

OSM_GARDEN = _ROOT / "data" / "gardens" / "sanyuan_osm.yaml"


class JiuzhouNorthTests(unittest.TestCase):
    def setUp(self):
        self.garden = config.load_garden(OSM_GARDEN)
        self.parts = dict(scene.build_garden(self.garden, OSM_GARDEN))
        self.fuhu = self.parts["water_40724042/water"]
        (self.fx0, self.fy0, _), (self.fx1, self.fy1, _) = self.fuhu.bounds()

    def test_nineteen_scenes(self):
        self.assertGreaterEqual(len(self.garden.scenes), 21)

    def test_ciyun_north_of_houhu(self):
        (cx0, cy0, _), (cx1, cy1, _) = self.parts["ciyun_puhu/ciyun_qianfochang/platform"].bounds()
        self.assertGreaterEqual(cy0, self.fy1)  # 慈云普护在后湖之北
        # 自鸣钟楼：两层体量，柱顶 = 台基 80 + 2×480 = 1040
        (_, _, z0), (_, _, z1) = self.parts["ciyun_puhu/ciyun_zhonglou/columns"].bounds()
        self.assertAlmostEqual(z1, 80.0 + 2 * 480.0, places=4)

    def test_shangtian_west_of_ciyun(self):
        (sx0, _, _), (sx1, _, _) = self.parts["shangtian_guang/shangtian_hanyue_lou/platform"].bounds()
        (cx0, _, _), (_, _, _) = self.parts["ciyun_puhu/ciyun_qianfochang/platform"].bounds()
        self.assertLess(sx1, cx0)  # 上下天光在慈云普护之西
        (_, _, _), (_, _, hz1) = self.parts["shangtian_guang/shangtian_hanyue_lou/columns"].bounds()
        self.assertAlmostEqual(hz1, 80.0 + 2 * 480.0, places=4)  # 两层敞阁

    def test_tantan_on_west_shore(self):
        (x0, _, _), (x1, _, _) = self.parts["tantan_dangdang/tantan_dian/platform"].bounds()
        self.assertLess(x1, self.fx0)  # 坦坦荡荡在后湖西岸之外
        for k in ("tantan_suxin/platform", "tantan_guangfeng/platform", "tantan_zhiyu/platform"):
            self.assertIn(f"tantan_dangdang/{k}", self.parts)


if __name__ == "__main__":
    unittest.main()
