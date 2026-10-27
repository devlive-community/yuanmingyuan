"""test_terrain.py — 地形水系单测：三角剖分、水面板、OSM 数据装载。"""

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "blender"))

from generator import terrain  # noqa: E402

WATER_JSON = _ROOT / "data" / "terrain" / "water_polygons.json"


class TriangulateTests(unittest.TestCase):
    def test_convex_square(self):
        tris = terrain.triangulate([(0, 0), (10, 0), (10, 10), (0, 10)])
        self.assertEqual(len(tris), 2)
        self.assertEqual(len({i for t in tris for i in t}), 4)

    def test_concave_polygon(self):
        # L 形（凹多边形）
        poly = [(0, 0), (20, 0), (20, 10), (10, 10), (10, 20), (0, 20)]
        tris = terrain.triangulate(poly)
        self.assertEqual(len(tris), 4)
        for t in tris:
            for i in t:
                self.assertIn(i, range(6))

    def test_winding_normalized(self):
        # 顺时针输入与逆时针输入三角化结果一致（自动统一绕序）
        a = terrain.triangulate([(0, 0), (10, 0), (10, 10), (0, 10)])
        b = terrain.triangulate([(0, 10), (10, 10), (10, 0), (0, 0)])
        self.assertEqual(len(a), len(b))


class PolygonSlabTests(unittest.TestCase):
    def test_slab_valid_and_depth(self):
        m = terrain.polygon_slab([(0, 0), (100, 0), (100, 50), (0, 50)])
        m.validate()
        (_, _, z0), (_, _, z1) = m.bounds()
        self.assertAlmostEqual(z1, 0.0)
        self.assertAlmostEqual(z0, -terrain.WATER_DEPTH_CM)

    def test_rejects_degenerate(self):
        with self.assertRaises(ValueError):
            terrain.polygon_slab([(0, 0), (10, 10)])


class OsmDataTests(unittest.TestCase):
    def test_load_named_filter(self):
        polys = terrain.load_polygons(WATER_JSON, ("福海", "后湖"))
        names = {p["name"] for p in polys}
        self.assertIn("福海", names)
        self.assertIn("后湖", names)
        self.assertEqual(len(polys), 2)
        fuhai = next(p for p in polys if p["name"] == "福海")
        self.assertGreater(fuhai["area_m2"], 250000)  # 福海 ≥ 25 公顷（真实量级）

    def test_load_by_id(self):
        polys = terrain.load_polygons(WATER_JSON, ("water_210654673",))
        self.assertEqual(len(polys), 1)

    def test_real_lake_point_count(self):
        polys = terrain.load_polygons(WATER_JSON, ("福海",))
        self.assertGreaterEqual(len(polys[0]["coords_cm"]), 10)  # 简化后仍有细节


if __name__ == "__main__":
    unittest.main()
