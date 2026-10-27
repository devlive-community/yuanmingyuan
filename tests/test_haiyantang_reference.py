"""海晏堂参考图效果版（非史料，ADR-0003）：构成与材质类。"""

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "blender"))

from generator import config, haiyantang_reference as ref, scene, western  # noqa: E402

SCENE = _ROOT / "data" / "scenes" / "haiyantang_reference.yaml"


class ReferenceSceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parts = scene.build_scene(config.load_scene(SCENE), SCENE)
        cls.labels = [label for label, _ in cls.parts]

    def test_meshes_valid(self):
        for _label, m in self.parts:
            m.validate()

    def test_no_historical_colour_classes(self):
        classes = {label.rsplit("/", 1)[1] for label in self.labels}
        self.assertTrue({"walls", "marble", "glazed_roof", "glazed_ridge"}.isdisjoint(classes))
        self.assertIn("limestone", classes)

    def test_twelve_bronze_figures_with_jets(self):
        for name in western.ZODIAC_SOUTH + western.ZODIAC_NORTH:
            self.assertIn(f"zodiac_{name}/bronze", self.labels)
            self.assertIn(f"zodiac_{name}/jet", self.labels)

    def test_figures_inside_pool(self):
        d = dict(self.parts)
        for name in western.ZODIAC_NORTH:
            (x0, y0, _), (x1, y1, _) = d[f"zodiac_{name}/limestone"].bounds()
            x, y = (x0 + x1) / 2.0 - ref.POOL_CX, (y0 + y1) / 2.0
            self.assertLess(abs(x / ref.POOL_RX) ** ref.POOL_SHAPE_N + abs(y / ref.POOL_RY) ** ref.POOL_SHAPE_N, 1.0)

    def test_pool_clear_of_stairs(self):
        d = dict(self.parts)
        (_, _, _), (_, ymax, _) = d["zodiac_pool/limestone"].bounds()
        stair_inner = western.UPPER_RUN_END_CM - western.CASCADE_W_CM
        self.assertLess(ymax, stair_inner)          # 导水台内缘


if __name__ == "__main__":
    unittest.main()
