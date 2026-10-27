"""test_sanyuan_osm.py — OSM 实测水系版总园单测（data/gardens/sanyuan_osm.yaml）。"""

import math
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "blender"))

from generator import config, scene  # noqa: E402

OSM_GARDEN = _ROOT / "data" / "gardens" / "sanyuan_osm.yaml"


class SanyuanOsmTests(unittest.TestCase):
    def setUp(self):
        self.garden = config.load_garden(OSM_GARDEN)
        self.parts = dict(scene.build_garden(self.garden, OSM_GARDEN))

    def test_water_from_osm_data(self):
        # 9 景 + 水面：OSM 实测 4 块（福海/后湖/方河/water_210654673）
        # ＋景内水面：万方安和/方壶胜境示意水面各 1；海晏堂 8（生肖池、锡海、楼南北喷水池 6）；
        # 远瀛观与大水法 3（海棠池、东西喷水塔池）
        self.assertGreaterEqual(len(self.garden.scenes), 21)
        self.assertIsNotNone(self.garden.terrain)
        water = [k for k in self.parts if k.endswith("/water")]
        self.assertEqual(len(water), 4 + 2 + 8 + 3)
        for label in ("water_18108375_210654679/water", "water_40724042/water", "water_210646474/water", "water_210654673/water",
                      "wanfang_anhe/water", "fanghu_shengjing/water", "haiyantang/zodiac_pool/water",
                      "haiyantang/tin_sea/water"):
            self.assertIn(label, water)

    def test_fuhai_water_is_large(self):
        (x0, y0, _), (x1, y1, _) = self.parts["water_18108375_210654679/water"].bounds()
        # 实测福海量级：数百米宽（摆位为锚点近似，只验外包尺寸）
        self.assertGreater(x1 - x0, 40000.0)  # ≥ 400 m
        self.assertGreater(y1 - y0, 30000.0)  # ≥ 300 m

    def test_jiuzhou_near_houhu(self):
        # 九洲清晏（后湖南岸）质心距后湖外包 < 150 m（锚点摆位近似）
        (bx0, by0, _), (bx1, by1, _) = self.parts["jiuzhou_qingyan/jiuzhou_qingyan_dian/platform"].bounds()
        (wx0, wy0, _), (wx1, wy1, _) = self.parts["water_40724042/water"].bounds()
        cx, cy = (bx0 + bx1) / 2.0, (by0 + by1) / 2.0
        dx = max(wx0 - cx, 0.0, cx - wx1)
        dy = max(wy0 - cy, 0.0, cy - wy1)
        self.assertLess(math.hypot(dx, dy), 15000.0)

    def test_pengdao_island_inside_fuhai(self):
        # 蓬岛瑶台岛台应落在福海水面外包内（福海中央）
        (ix0, iy0, _), (ix1, iy1, _) = self.parts["pengdao_yaotai/island"].bounds()
        (wx0, wy0, _), (wx1, wy1, _) = self.parts["water_18108375_210654679/water"].bounds()
        self.assertGreaterEqual(ix0, wx0)
        self.assertLessEqual(ix1, wx1)
        self.assertGreaterEqual(iy0, wy0)
        self.assertLessEqual(iy1, wy1)


if __name__ == "__main__":
    unittest.main()
