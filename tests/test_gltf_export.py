"""test_gltf_export.py — GLB 写出器的结构、换算与三角化断言。"""

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))

from generator import gltf, mesh  # noqa: E402


def make_primitives():
    box = mesh.box(4272.0, 1699.2, 0.0, 112.0)            # 台基（cm）
    col = mesh.cylinder(0.0, 100.0, 28.8, segments=8)     # 100 cm 高柱（cm）
    return [
        gltf.Primitive("platform", box, (0.6, 0.6, 0.6)),
        gltf.Primitive("柱网", col, (0.5, 0.1, 0.1)),
    ]


class GlbWriterTests(unittest.TestCase):
    def test_container_structure(self):
        blob = gltf.build_glb(make_primitives())
        self.assertEqual(len(blob) % 4, 0)                 # GLB 容器 4 字节对齐
        version, doc, bin_data = gltf.parse_glb(blob)
        self.assertEqual(version, 2)
        self.assertEqual(len(bin_data), doc["buffers"][0]["byteLength"])
        self.assertEqual(doc["asset"]["version"], "2.0")
        self.assertEqual(len(doc["meshes"]), 2)
        self.assertEqual(len(doc["nodes"]), 2)
        self.assertEqual(doc["nodes"][0]["name"], "platform")

    def test_accessor_counts_and_triangulation(self):
        _, doc, _ = gltf.parse_glb(gltf.build_glb(make_primitives()))
        for m, prim in zip(doc["meshes"], make_primitives()):
            self.assertEqual(len(m["primitives"]), 1)
            p = m["primitives"][0]
            self.assertEqual(p["mode"], 4)
            pos_acc = doc["accessors"][p["attributes"]["POSITION"]]
            idx_acc = doc["accessors"][p["indices"]]
            self.assertEqual(pos_acc["count"], len(prim.mesh.vertices))
            self.assertEqual(pos_acc["type"], "VEC3")
            # 扇形三角化：n 边形 → n−2 三角形，索引数 = 3 × (Σ边数 − 2×面数)
            tris = sum(len(f) - 2 for f in prim.mesh.faces)
            self.assertEqual(idx_acc["count"], tris * 3)
            self.assertIn("min", pos_acc)
            self.assertIn("max", pos_acc)

    def test_unit_and_axis_conversion(self):
        """cm→m、Z-up→Y-up：柱高 100 cm → Y 0→1.0 m；进深 y → glTF −z。"""
        _, doc, _ = gltf.parse_glb(gltf.build_glb(make_primitives()))
        box_acc = doc["accessors"][doc["meshes"][0]["primitives"][0]["attributes"]["POSITION"]]
        col_acc = doc["accessors"][doc["meshes"][1]["primitives"][0]["attributes"]["POSITION"]]
        self.assertAlmostEqual(box_acc["max"][0], 21.36, places=6)    # x/100
        self.assertAlmostEqual(box_acc["max"][1], 1.12, places=6)     # z(台基高)/100
        self.assertAlmostEqual(box_acc["min"][2], -8.496, places=6)   # −y/100
        self.assertAlmostEqual(col_acc["min"][1], 0.0, places=6)
        self.assertAlmostEqual(col_acc["max"][1], 1.0, places=6)      # 柱高 1 m

    def test_alignment_and_double_sided(self):
        _, doc, _ = gltf.parse_glb(gltf.build_glb(make_primitives()))
        for view in doc["bufferViews"]:
            self.assertEqual(view["byteOffset"] % 4, 0)
        for mat in doc["materials"]:
            self.assertTrue(mat["doubleSided"])
            self.assertEqual(mat["pbrMetallicRoughness"]["metallicFactor"], 0.0)

    def test_rejects_invalid_mesh(self):
        bad = mesh.Mesh(vertices=[(0.0, 0.0, 0.0)], faces=[(0, 0, 0)])
        with self.assertRaises(ValueError):
            gltf.build_glb([gltf.Primitive("坏网格", bad, (1, 1, 1))])


if __name__ == "__main__":
    unittest.main()
