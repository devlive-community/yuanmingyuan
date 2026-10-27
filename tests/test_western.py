"""test_western.py — 西洋楼 v3 单测：海晏堂按铜版画四面 + 样式雷图说 + 考古 + OSM 重建。

断言以 docs/sources/research-haiyantang.md v3 的有据项为主（朝向、间数、门窗数、锡海尺寸、
生肖次序、导水台数），尺寸推定项（S-023）只断言构件间的相对关系。
"""

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "blender"))

from generator import config, scene, western  # noqa: E402

HAIYANTANG_SCENE = _ROOT / "data" / "scenes" / "haiyantang.yaml"
YYG_SCENE = _ROOT / "data" / "scenes" / "yuanyingguan_dashuifa.yaml"


class HipRoofTests(unittest.TestCase):
    def test_bounds_and_ridge(self):
        m = western.hip_roof(5000.0, 1500.0, 400.0, z0=1150.0)
        m.validate()
        (x0, y0, z0), (x1, y1, z1) = m.bounds()
        self.assertAlmostEqual(x1 - x0, 5000.0)
        self.assertAlmostEqual(y1 - y0, 1500.0)
        self.assertAlmostEqual(z1, 1550.0)
        ridge = [v for v in m.vertices if abs(v[2] - z1) < 1e-6]
        self.assertAlmostEqual(ridge[1][0] - ridge[0][0], 3500.0)

    def test_hip_roof_xy_long_side_along_y(self):
        m = western.hip_roof_xy(100.0, 0.0, 1000.0, 5000.0, 0.0, 300.0)
        (x0, y0, _), (x1, y1, _) = m.bounds()
        self.assertAlmostEqual(x1 - x0, 1000.0, places=6)
        self.assertAlmostEqual(y1 - y0, 5000.0, places=6)
        self.assertAlmostEqual((x0 + x1) / 2, 100.0, places=6)


class HelperTests(unittest.TestCase):
    def test_obox_diagonal(self):
        m = western.obox(0.0, 0.0, 300.0, 400.0, 20.0, 0.0, 50.0)
        m.validate()
        (x0, y0, _), (x1, y1, _) = m.bounds()
        self.assertGreater(x1 - x0, 300.0)   # 长 500 沿斜向
        self.assertGreater(y1 - y0, 400.0)

    def test_flight_steps_descend(self):
        m = western.flight(0.0, 0.0, 1000.0, 0.0, 300.0, 500.0, 0.0, 10)
        m.validate()
        (_, _, z0), (_, _, z1) = m.bounds()
        self.assertAlmostEqual(z0, 0.0)
        self.assertAlmostEqual(z1, 475.0)    # 首级顶 = 起点 − 半级


class HaiyantangSceneTests(unittest.TestCase):
    def setUp(self):
        self.sc = config.load_scene(HAIYANTANG_SCENE)
        self.parts = dict(scene.build_scene(self.sc, HAIYANTANG_SCENE))

    def bounds(self, label):
        return self.parts[label].bounds()

    def test_all_parts_valid_and_english_labels(self):
        self.assertEqual(self.sc.special, "haiyantang")
        for label, m in self.parts.items():
            m.validate()
            self.assertTrue(label.isascii(), label)

    def test_faces_west(self):
        # 坐东面西：生肖池在正楼之西，蓄水楼在正楼之东
        (_, _, _), (pool_x1, _, _) = self.bounds("zodiac_pool/water")
        (hall_x0, _, _), (hall_x1, _, _) = self.bounds("front_building/walls")
        (res_x0, _, _), _ = self.bounds("reservoir_hall/walls")
        self.assertLess(pool_x1, hall_x0)
        self.assertGreater(res_x0, hall_x1)

    def test_main_hall_eleven_bays_two_storeys(self):
        self.assertEqual(sum(western.MAIN_SEGMENT_BAYS), 11)
        # 每间上下各一洞口（玻璃退进墙皮）：上层为券口窗，故玻璃轮廓顶点多于方窗
        self.assertGreater(len(self.parts["front_building/windows"].vertices), 22 * 8)
        (x0, _, _), (x1, _, _) = self.parts["front_building/windows"].bounds()
        (fx0, _, _), _ = self.parts["front_building/facade/walls"].bounds()
        self.assertGreater(x0, fx0)                       # 玻璃在墙皮外皮之内（退进）
        self.assertLess(western.FLOOR2_CM, western.MAIN_EAVE_CM)

    def test_reservoir_thirteen_bays_three_doors(self):
        self.assertEqual(2 * western.RES_END_BAYS + western.RES_MID_BAYS, 13)
        # 南北两面 × 13 间：每面 10 方窗（8 顶点）+ 3 券门
        win = self.parts["reservoir_hall/windows"]
        self.assertEqual(len(win.vertices) - 2 * 3 * (2 * (3 + western.ARCH_SEGMENTS - 1 + 1)), 2 * 10 * 8)
        (x0, y0, _), (x1, y1, z1) = self.bounds("reservoir_hall/walls")
        self.assertAlmostEqual(x1 - x0, 5560.0)       # OSM 遗址轮廓
        self.assertAlmostEqual(y1 - y0, 2500.0)
        self.assertAlmostEqual(z1, western.RES_EAVE_CM)

    def test_tin_sea_on_roof(self):
        (x0, y0, z0), (x1, y1, _) = self.bounds("tin_sea/water")
        self.assertAlmostEqual(x1 - x0, 2736.0)        # 27.36 m
        self.assertAlmostEqual(y1 - y0, 572.0)         # 5.72 m
        self.assertGreaterEqual(z0, western.RES_EAVE_CM)
        self.assertLessEqual(x1 - x0, western.RES_MID_LEN_CM)   # 容于中段

    def test_waterwheel_houses_at_both_ends(self):
        (wx0, _, wz0), (wx1, _, _) = self.bounds("waterwheel_house_west/walls")
        (ex0, _, _), _ = self.bounds("waterwheel_house_east/walls")
        self.assertLess(wx1, 0.0)
        self.assertGreater(ex0, 0.0)
        self.assertAlmostEqual(wz0, western.RES_EAVE_CM)

    def test_zodiac_order_and_sides(self):
        south = [f"zodiac_{n}/marble" for n in western.ZODIAC_SOUTH]
        north = [f"zodiac_{n}/marble" for n in western.ZODIAC_NORTH]
        self.assertEqual(western.ZODIAC_SOUTH[0], "rat")
        self.assertEqual(western.ZODIAC_NORTH[0], "ox")
        for labels, sign in ((south, -1.0), (north, 1.0)):
            xs = []
            for label in labels:
                (x0, y0, _), (x1, y1, _) = self.bounds(label)
                self.assertGreater(sign * (y0 + y1) / 2.0, 0.0)
                xs.append((x0 + x1) / 2.0)
            self.assertEqual(xs, sorted(xs, reverse=True))   # 由内（东）向外（西）
        self.assertEqual(len([k for k in self.parts if k.endswith("/bronze") and k.startswith("zodiac_")]), 12)

    def test_zodiac_outside_pool(self):
        (px0, py0, _), (px1, py1, _) = self.bounds("zodiac_pool/water")
        for name in western.ZODIAC_SOUTH + western.ZODIAC_NORTH:
            (x0, y0, _), (x1, y1, _) = self.bounds(f"zodiac_{name}/marble")
            # 石台在池水面外包之外，或至少不落在八字墙内侧：以到池轴距离大于该处池半宽判定
            xc, yc = (x0 + x1) / 2.0, abs((y0 + y1) / 2.0)
            t = (western.POOL_BACK_X - xc) / (western.POOL_BACK_X - western.POOL_SHOULDER_X)
            wall_y = western.POOL_BACK_HALF_CM + t * (western.POOL_HALF_CM - western.POOL_BACK_HALF_CM)
            self.assertGreater(yc - 45.0, wall_y + western.POOL_WALL_T_CM / 2.0)

    def test_stairs_reach_upper_floor_and_cascades(self):
        (_, _, _), (_, _, z1) = self.bounds("west_stairs/marble")
        self.assertGreaterEqual(z1, western.FLOOR2_CM)
        # 导水台两侧共六十（每侧下跑每级一个）
        self.assertEqual(len(self.parts["west_stairs/cascade"].vertices), 60 * 8)
        (_, _, _), (_, _, ez1) = self.bounds("east_stairs/marble")
        self.assertAlmostEqual(ez1, western.RES_EAVE_CM)   # 东梯登顶

    def test_garden_fountains(self):
        names = [k for k in self.parts if k.startswith("fountain_") and k.endswith("/water")]
        self.assertEqual(len(names), 6)   # 南北各二八角池 + 中央圆池



class YuanyingguanDashuifaTests(unittest.TestCase):
    """远瀛观·大水法·观水法：南北一线、石龛背靠高台、七级水台、十犬一鹿、十三层塔、五扇石屏。"""

    def setUp(self):
        self.sc = config.load_scene(YYG_SCENE)
        self.parts = dict(scene.build_scene(self.sc, YYG_SCENE))

    def center_y(self, label):
        (_, y0, _), (_, y1, _) = self.parts[label].bounds()
        return (y0 + y1) / 2.0

    def test_valid_and_english_labels(self):
        self.assertEqual(self.sc.special, "yuanyingguan_dashuifa")
        for label, m in self.parts.items():
            m.validate()
            self.assertTrue(label.isascii(), label)

    def test_north_south_axis(self):
        # 北远瀛观 > 中大水法 > 南观水法
        self.assertGreater(self.center_y("yuanyingguan/walls"), self.center_y("dashuifa_niche/marble"))
        self.assertGreater(self.center_y("dashuifa_niche/marble"), self.center_y("guanshuifa/marble"))

    def test_niche_backs_onto_terrace(self):
        (_, _, _), (_, niche_y1, _) = self.parts["dashuifa_niche/marble"].bounds()
        self.assertAlmostEqual(niche_y1, western.YY_TERRACE_Y0)

    def test_yuanyingguan_on_terrace_with_gold_roof(self):
        (_, _, z0), _ = self.parts["yuanyingguan/walls"].bounds()
        self.assertAlmostEqual(z0, western.YY_TERRACE_H_CM)
        self.assertIn("yuanyingguan/gold_roof", self.parts)

    def test_counts_from_records(self):
        self.assertEqual(western.DSF_CASCADE_TIERS, 7)
        self.assertEqual(len(self.parts["hounds_west/bronze"].vertices), 5 * 8)
        self.assertEqual(len(self.parts["hounds_east/bronze"].vertices), 5 * 8)
        self.assertEqual(western.DSF_TOWER_TIERS, 13)
        self.assertEqual(western.GSF_SCREEN_PANELS, 5)

    def test_towers_flank_pool(self):
        (px0, _, _), (px1, _, _) = self.parts["dashuifa_pool/water"].bounds()
        (_, _, _), (wx1, _, _) = self.parts["fountain_tower_west/water"].bounds()
        (ex0, _, _), _ = self.parts["fountain_tower_east/water"].bounds()
        self.assertLess(wx1, px0)
        self.assertGreater(ex0, px1)


if __name__ == "__main__":
    unittest.main()
