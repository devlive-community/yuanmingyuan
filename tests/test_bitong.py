"""test_bitong.py — 碧桐书院 + 九洲环湖闭环单测。"""

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "blender"))

from generator import config, scene  # noqa: E402

OSM_GARDEN = _ROOT / "data" / "gardens" / "sanyuan_osm.yaml"


class BitongTests(unittest.TestCase):
    def setUp(self):
        self.garden = config.load_garden(OSM_GARDEN)
        self.parts = dict(scene.build_garden(self.garden, OSM_GARDEN))
        (self.fx0, self.fy0, _), (self.fx1, self.fy1, _) = self.parts["water_40724042/water"].bounds()

    def test_three_courtyard_axis(self):
        # 三进院落：前殿 → 中殿 → 后殿（南→北）
        spans = {}
        for key in ("bitong_qiandian", "bitong_zhongdian", "bitong_houdian"):   # 前殿 / 中殿 / 后殿
            (_, y0, _), (_, y1, _) = self.parts[f"bitong_shuyuan/{key}/platform"].bounds()
            spans[key] = (y0, y1)
        self.assertLess(spans["bitong_qiandian"][1], spans["bitong_zhongdian"][0])
        self.assertLess(spans["bitong_zhongdian"][1], spans["bitong_houdian"][0])
        # 中殿五楹：181D + 42D = 223D × 8 = 1784（rot 0，面阔沿 X）
        (x0, _, _), (x1, _, _) = self.parts["bitong_shuyuan/bitong_zhongdian/platform"].bounds()
        self.assertAlmostEqual(x1 - x0, 1784.0, places=4)

    def test_binong_ne_corner(self):
        (x0, y0, _), (x1, y1, _) = self.parts["bitong_shuyuan/bitong_zhongdian/platform"].bounds()
        self.assertGreater(x0, self.fx1)   # 后湖东界之外
        self.assertGreater(y0, self.fy1)   # 后湖北界之外（东北角）
        # 云岑亭在西侧
        (tx0, _, _), (tx1, _, _) = self.parts["bitong_shuyuan/bitong_yuncen_ting/platform"].bounds()
        self.assertLess(tx0, x0)


class JiuzhouRingClosureTests(unittest.TestCase):
    """九洲环湖闭环：后湖四周八景 + 南岸九洲清晏，全部就位。"""

    def test_all_ring_scenes_present(self):
        g = config.load_garden(OSM_GARDEN)
        parts = dict(scene.build_garden(g, OSM_GARDEN))
        ring = [
            "jiuzhou_qingyan",   # 九洲清晏（南）
            "louyue_kaiyun",     # 镂月开云（东南）
            "tianran_tuhua",     # 天然图画（东）
            "bitong_shuyuan",    # 碧桐书院（东北）
            "ciyun_puhu",        # 慈云普护（北）
            "shangtian_guang",   # 上下天光（北偏西）
            "xinghua_chunjuan",  # 杏花春馆（西北）
            "ruyu_hangjin",      # 茹古涵今（西）
            "tantan_dangdang",   # 坦坦荡荡（西）
        ]
        names = {k.split("/")[0] for k in parts}
        for n in ring:
            self.assertIn(n, names)

    def test_ring_scenes_around_lake(self):
        g = config.load_garden(OSM_GARDEN)
        parts = dict(scene.build_garden(g, OSM_GARDEN))
        (fx0, fy0, _), (fx1, fy1, _) = parts["water_40724042/water"].bounds()
        cx, cy = (fx0 + fx1) / 2.0, (fy0 + fy1) / 2.0
        # 代表建筑与湖心的相对方位
        checks = {
            "bitong_shuyuan/bitong_zhongdian/platform": ("east", "north"),
            "tianran_tuhua/tianran_fanglou/platform": ("east", None),
            "tantan_dangdang/tantan_dian/platform": ("west", None),
            "ciyun_puhu/ciyun_qianfochang/platform": (None, "north"),
            "shangtian_guang/shangtian_hanyue_lou/platform": (None, "north"),
        }
        for label, (ew, ns) in checks.items():
            (bx0, by0, _), (bx1, by1, _) = parts[label].bounds()
            bx, by = (bx0 + bx1) / 2.0, (by0 + by1) / 2.0
            if ew == "east":
                self.assertGreater(bx, cx, label)
            if ew == "west":
                self.assertLess(bx, cx, label)
            if ns == "north":
                self.assertGreater(by, cy, label)


if __name__ == "__main__":
    unittest.main()
