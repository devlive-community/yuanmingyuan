"""test_geometry.py — 平面几何 / 台基 / 柱网 / 各类屋顶的尺寸断言。

基准参数：七等斗口 3.0 寸（D = 9.6 cm）、面阔 7 间（明间平身科 6）、
进深 3 间（平身科 4）、台基高 3.5 尺。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))

from generator import brackets, columns, config, mesh, plan, platform, roof, units  # noqa: E402
from generator.assemble import build_building_parts  # noqa: E402

D = 9.6  # 斗口 cm


def make_params(**kw) -> config.BuildingParams:
    base = dict(
        id="t", name="测试殿", grade="大式", doukou_cun=3.0,
        bays=7, depth_bays=3, bay_brackets=6, depth_brackets=4,
        roof="歇山", platform_height_chi=3.5,
    )
    base.update(kw)
    return config.BuildingParams(**base)


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.p = make_params()
        self.pl = plan.build_plan(self.p)

    def test_bay_widths(self):
        ming = (11 * 6 + 1) * D   # 643.2
        side = (11 * 5 + 1) * D   # 537.6
        expected = (side, side, side, ming, side, side, side)
        self.assertEqual(len(self.pl.bay_widths), len(expected))
        for got, want in zip(self.pl.bay_widths, expected):
            self.assertAlmostEqual(got, want, places=6)
        self.assertAlmostEqual(self.pl.length, ming + 6 * side, places=6)
        self.assertAlmostEqual(self.pl.width, 3 * (11 * 4 + 1) * D, places=6)

    def test_eave_projection(self):
        self.assertAlmostEqual(self.pl.upper_eave_cm, 21 * D)
        self.assertAlmostEqual(self.pl.eave_length, self.pl.length + 2 * 21 * D)
        self.assertAlmostEqual(self.pl.eave_width, self.pl.width + 2 * 21 * D)

    def test_column_positions(self):
        eave = plan.eave_columns(self.pl)
        gold = plan.gold_columns(self.pl)
        # 檐柱：面阔分位 8 × 前后檐 2 + 两山内分位 2 × 2 = 20
        self.assertEqual(len(eave), 20)
        # 金柱：面阔内分位 6 × 进深内分位 2 = 12
        self.assertEqual(len(gold), 12)
        # 角柱不重复
        self.assertEqual(len(set(eave)), len(eave))
        # 前檐柱 Y = −W/2（正面朝 −Y）
        front = {p for p in eave if abs(p[1] + self.pl.width / 2) < 1e-6}
        self.assertEqual(len(front), 8)

    def test_rejects_even_bays(self):
        with self.assertRaises(ValueError):
            plan.build_plan(make_params(bays=6))


class PlatformTests(unittest.TestCase):
    def test_platform_box(self):
        pl = plan.build_plan(make_params())
        m = platform.build_platform(pl, 112.0)
        m.validate()
        (xmin, ymin, zmin), (xmax, ymax, zmax) = m.bounds()
        self.assertAlmostEqual(zmin, 0.0)
        self.assertAlmostEqual(zmax, 112.0)
        # 台明 = 柱中外扩一个上檐出（S-001）
        self.assertAlmostEqual(xmax - xmin, pl.eave_length)
        self.assertAlmostEqual(ymax - ymin, pl.eave_width)
        self.assertEqual(len(m.vertices), 8)
        self.assertEqual(len(m.faces), 6)


class MoonPlatformTests(unittest.TestCase):
    """月台＋三路九级踏跺（正大光明殿记载；几何参数为工作假设 S-015）。"""

    def setUp(self):
        self.p = make_params(moon_platform=True, stairs_flights=3, stairs_steps=9)
        self.pl = plan.build_plan(self.p)
        self.m = platform.build_platform(self.pl, 112.0, self.p)

    def test_bounds_and_extents(self):
        self.m.validate()
        (_, ymin, _), (_, _, zmax) = self.m.bounds()
        self.assertAlmostEqual(zmax, 112.0)
        expected_ymin = -(
            self.pl.eave_width / 2.0
            + platform.STAGE_DEPTH_CM
            + 9 * platform.STAIR_TREAD_CM
        )
        self.assertAlmostEqual(ymin, expected_ymin)
        # 对比无月台情形：只有台明
        m2 = platform.build_platform(self.pl, 112.0)
        (_, ymin2, _), _ = m2.bounds()
        self.assertAlmostEqual(ymin2, -self.pl.eave_width / 2.0)

    def test_step_levels(self):
        zs = {round(v[2], 6) for v in self.m.vertices}
        rise = 112.0 / 9
        for k in range(9):  # 九级，每级顶面 = 112 − k·rise
            self.assertIn(round(112.0 - k * rise, 6), zs)

    def test_component_counts(self):
        # 台明 8 + 月台 8 + 27 级台阶盒 216 + 6 垂带 48
        self.assertEqual(len(self.m.vertices), 280)
        # 台明 6 + 月台 6 + 27×6 + 6×6
        self.assertEqual(len(self.m.faces), 6 + 6 + 27 * 6 + 6 * 6)


class RoundRidgeRoofTests(unittest.TestCase):
    """卷棚歇山：无正脊方棱，罗锅圆脊以半圆柱面近似（S-014）。"""

    def setUp(self):
        self.pl = plan.build_plan(make_params(roof="卷棚歇山"))
        self.z_base = 112.0 + 60 * D
        self.m = roof.build_roof_xieshan(self.pl, self.z_base, style="卷棚歇山")

    def test_mesh_valid(self):
        self.m.validate()

    def test_no_ridge_box_and_round_top(self):
        half = self.pl.eave_width / 2.0
        ridge_z = (half / D) / 4 * (0.5 + 0.65 + 0.75 + 0.9) * D
        (_, _, _), (_, _, zmax) = self.m.bounds()
        # 脊顶 = 脊线高 + 罗锅半径（1.5 斗口），低于尖山的正脊盒顶
        self.assertAlmostEqual(zmax, self.z_base + ridge_z + 1.5 * D)

    def test_style_aliases(self):
        m2 = roof.build_roof_xieshan(self.pl, self.z_base, style="卷棚")
        self.assertEqual(len(m2.vertices), len(self.m.vertices))
        with self.assertRaises(ValueError):
            roof.build_roof_xieshan(self.pl, self.z_base, style="庑殿")


def _face_normal(m: mesh.Mesh, f) -> tuple[float, float, float]:
    """Newell 法向（未归一化）。"""
    nx = ny = nz = 0.0
    for i, a in enumerate(f):
        x0, y0, z0 = m.vertices[a]
        x1, y1, z1 = m.vertices[f[(i + 1) % len(f)]]
        nx += (y0 - y1) * (z0 + z1)
        ny += (z0 - z1) * (x0 + x1)
        nz += (x0 - x1) * (y0 + y1)
    return nx, ny, nz


def _signed_volume(m: mesh.Mesh) -> float:
    """闭合网格有向体积（外法向一致时为正）。"""
    v = 0.0
    for f in m.faces:
        a = m.vertices[f[0]]
        for k in range(1, len(f) - 1):
            b, c = m.vertices[f[k]], m.vertices[f[k + 1]]
            v += (a[0] * (b[1] * c[2] - b[2] * c[1])
                  - a[1] * (b[0] * c[2] - b[2] * c[0])
                  + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6.0
    return v


RIDGE_Z_4STEP = (0.5 + 0.65 + 0.75 + 0.9) / 4   # 脊高 / 半跨（四步均分，S-003）


class RoofDispatchTests(unittest.TestCase):
    def test_xieshan_matches_direct_call(self):
        pl = plan.build_plan(make_params())
        a = roof.build_roof(pl, 100.0, "卷棚歇山")
        b = roof.build_roof_xieshan(pl, 100.0, style="卷棚")
        self.assertEqual(a.vertices, b.vertices)

    def test_unknown_type(self):
        pl = plan.build_plan(make_params())
        with self.assertRaises(ValueError):
            roof.build_roof(pl, 100.0, "盝顶")


class WudianRoofTests(unittest.TestCase):
    """庑殿：四坡举架、45° 垂脊、无推山（S-038）。"""

    def setUp(self):
        self.pl = plan.build_plan(make_params(roof="庑殿"))
        self.z_base = 112.0 + 60 * D
        self.m = roof.build_roof_wudian(self.pl, self.z_base)

    def test_valid_and_slopes_face_up(self):
        self.m.validate()
        shell = roof._hipped_shell(roof._profile_cm(self.pl, 4), self.pl.eave_length / 2, self.pl.eave_width / 2)
        # 四坡各 4 步：前后 4 梯形 ×2、两山 3 梯形 + 1 三角 ×2
        self.assertEqual(len(shell.faces), 16)
        for f in shell.faces:
            self.assertGreater(_face_normal(shell, f)[2], 0.0)

    def test_ridge_length_and_height(self):
        hx, hy = self.pl.eave_length / 2, self.pl.eave_width / 2
        ridge_z = self.z_base + hy * RIDGE_Z_4STEP
        top = [(x, y) for (x, y, z) in self.m.vertices if abs(z - ridge_z) < 1e-6 and abs(y) < 1e-6]
        self.assertAlmostEqual(max(abs(x) for x, _ in top), hx - hy)   # 正脊半长
        (_, _, _), (xmax, ymax, zmax) = self.m.bounds()
        self.assertAlmostEqual(xmax, hx)
        self.assertAlmostEqual(ymax, hy)
        self.assertAlmostEqual(zmax, ridge_z + 2 * D)

    def test_rejects_square_plan(self):
        sq = plan.build_plan(make_params(bays=1, depth_bays=1, bay_brackets=4, depth_brackets=4))
        with self.assertRaises(ValueError):
            roof.build_roof_wudian(sq, 100.0)


class CuanjianRoofTests(unittest.TestCase):
    """四角攒尖：方亭（面阔 = 进深），四坡收于一点，宝顶圆柱近似（S-038）。"""

    def setUp(self):
        self.p = make_params(roof="攒尖", bays=1, depth_bays=1, bay_brackets=4, depth_brackets=4)
        self.pl = plan.build_plan(self.p)
        self.m = roof.build_roof_cuanjian(self.pl, 500.0)

    def test_apex_and_finial(self):
        self.m.validate()
        h = self.pl.eave_length / 2
        apex = 500.0 + h * RIDGE_Z_4STEP
        (xmin, _, zmin), (xmax, _, zmax) = self.m.bounds()
        self.assertAlmostEqual(zmin, 500.0)
        self.assertAlmostEqual(xmax, h)
        self.assertAlmostEqual(zmax, apex + 6 * D)
        apex_verts = [v for v in self.m.vertices if abs(v[2] - apex) < 1e-6 and abs(v[0]) < 1e-6]
        self.assertEqual(len(apex_verts), 1)   # 四坡收于同一顶点（已合并）

    def test_rejects_rectangular_plan(self):
        with self.assertRaises(ValueError):
            roof.build_roof_cuanjian(plan.build_plan(make_params()), 500.0)


class GableRoofTests(unittest.TestCase):
    """硬山 / 悬山（S-038）。"""

    def setUp(self):
        self.pl = plan.build_plan(make_params(bays=5, depth_bays=2))
        self.z_base = 112.0 + 60 * D

    def test_yingshan_flush_with_wall(self):
        m = roof.build_roof_yingshan(self.pl, self.z_base, wall_base_cm=112.0)
        m.validate()
        (xmin, _, zmin), (xmax, ymax, _) = m.bounds()
        self.assertAlmostEqual(xmax, self.pl.length / 2 + 6 * D)   # 屋面止于山墙外皮
        self.assertAlmostEqual(xmin, -xmax)
        self.assertAlmostEqual(zmin, 112.0)                         # 山墙落台基顶
        self.assertAlmostEqual(ymax, self.pl.eave_width / 2)        # 前后檐照常出檐

    def test_yingshan_wall_is_closed_solid(self):
        half = self.pl.eave_width / 2
        prof = roof._profile_cm(self.pl, 4)
        outline = roof._gable_outline(prof, half, self.pl.width / 2 + 6 * D, -60 * D)
        wall = roof._gable_slab(outline, -60 * D, 0.0, 9 * D)
        wall.validate()
        self.assertGreater(_signed_volume(wall), 0.0)
        self.assertGreater(_signed_volume(wall.mirrored("x")), 0.0)
        # 山尖顶点 = 脊高
        self.assertAlmostEqual(max(z for _, z in outline), half * RIDGE_Z_4STEP)

    def test_xuanshan_overhang(self):
        m = roof.build_roof_xuanshan(self.pl, self.z_base, style="卷棚")
        m.validate()
        (_, _, zmin), (xmax, _, zmax) = m.bounds()
        self.assertAlmostEqual(xmax, self.pl.length / 2 + 8 * D)   # 出梢
        self.assertAlmostEqual(zmin, self.z_base)                   # 无山墙，不低于檐口
        ridge_z = self.z_base + self.pl.eave_width / 2 * RIDGE_Z_4STEP
        self.assertAlmostEqual(zmax, ridge_z + 1.5 * D)             # 卷棚罗锅脊

    def test_assemble_all_types(self):
        from generator.assemble import build_building_meshes
        cases = {
            "庑殿": {}, "硬山": {}, "卷棚硬山": {}, "悬山": {}, "卷棚悬山": {},
            "攒尖": dict(bays=1, depth_bays=1, bay_brackets=4, depth_brackets=4),
        }
        for r, kw in cases.items():
            with self.subTest(roof=r):
                *_, m_roof, _pl = build_building_meshes(make_params(roof=r, double_eave=True, **kw))
                m_roof.validate()


def make_xiaoshi(**kw) -> config.BuildingParams:
    base = dict(
        id="x", name="测试小式", grade="小式", bays=3, depth_bays=1,
        ming_bay_chi=10.0, depth_bay_chi=12.0, roof="卷棚硬山", platform_height_chi=1.5,
    )
    base.update(kw)
    return config.BuildingParams(**base)


class XiaoshiPlanTests(unittest.TestCase):
    """小式：明间面宽驱动（S-039）。明间 10 尺 = 320 cm。"""

    def setUp(self):
        self.pl = plan.build_plan(make_xiaoshi())

    def test_proportions(self):
        col_h = 320.0 * 0.8                                   # 柱高 = 明间 × 0.8
        self.assertAlmostEqual(self.pl.column_height_cm, col_h)
        self.assertAlmostEqual(self.pl.eave_column_diameter_cm, col_h / 11)
        self.assertAlmostEqual(self.pl.gold_column_diameter_cm, col_h / 11 + 3.2)  # +1 寸
        self.assertAlmostEqual(self.pl.upper_eave_cm, col_h * 0.3)
        self.assertAlmostEqual(self.pl.doukou_cm, col_h / 11 / 6)                  # 等效模数

    def test_bays(self):
        self.assertEqual(self.pl.bay_widths, (256.0, 320.0, 256.0))   # 次间缺省 0.8 明间
        self.assertEqual(self.pl.depth_widths, (384.0,))
        pl2 = plan.build_plan(make_xiaoshi(side_bay_chi=9.0))
        self.assertAlmostEqual(pl2.bay_widths[0], 288.0)

    def test_columns_follow_plan(self):
        m = columns.build_columns(self.pl, 48.0)
        (_, _, _), (_, _, zmax) = m.bounds()
        self.assertAlmostEqual(zmax, 48.0 + 256.0)

    def test_square_pavilion_with_cuanjian(self):
        """各间等宽的三间方亭可用攒尖。"""
        from generator.assemble import build_building_meshes
        p = make_xiaoshi(bays=3, depth_bays=3, ming_bay_chi=8.0, side_bay_chi=8.0,
                         depth_bay_chi=8.0, roof="攒尖")
        *_, m_roof, pl = build_building_meshes(p)
        m_roof.validate()
        self.assertAlmostEqual(pl.length, pl.width)

    def test_validation(self):
        with self.assertRaises(ValueError):
            make_xiaoshi(ming_bay_chi=None).validate()
        with self.assertRaises(ValueError):
            make_xiaoshi(depth_bay_chi=0.0).validate()
        with self.assertRaises(ValueError):
            make_xiaoshi(side_bay_chi=-1.0).validate()
        with self.assertRaises(ValueError):
            make_xiaoshi(grade="中式").validate()
        make_xiaoshi().validate()                 # 小式不需要斗口


class BracketTests(unittest.TestCase):
    """斗拱层（S-002 修正，S-040）。基准 D = 9.6 cm。"""

    def test_tiao_count(self):
        self.assertEqual(brackets.tiao_count("一斗三升"), 0)
        self.assertEqual(brackets.tiao_count("三踩"), 1)
        self.assertEqual(brackets.tiao_count("五踩重昂"), 2)
        self.assertEqual(brackets.tiao_count("九踩"), 4)
        with self.assertRaises(ValueError):
            brackets.tiao_count("十一踩")

    def test_projection_and_height(self):
        self.assertAlmostEqual(brackets.projection_cm(D, 2), 6 * D)        # 五踩出踩 2 拽架
        self.assertAlmostEqual(brackets.layer_height_cm(D, 2), 10 * D)     # 平板枋 2 + 4 层 × 2

    def test_layer_mesh(self):
        pl = plan.build_plan(make_params())
        top = 112.0 + 60 * D
        m = brackets.build_brackets(pl, top, 2)
        m.validate()
        (xmin, ymin, zmin), (xmax, ymax, zmax) = m.bounds()
        self.assertAlmostEqual(zmin, top)
        self.assertAlmostEqual(zmax, top + 10 * D)
        # 最外为末跳翘头 / 耍头：檐柱中 + 出踩 + 半个坐斗（伸出挑檐枋外）
        self.assertAlmostEqual(ymax, pl.width / 2 + 6 * D + 1.5 * D)
        self.assertAlmostEqual(xmax, pl.length / 2 + 6 * D + 1.5 * D)

    def test_set_positions_spacing(self):
        pl = plan.build_plan(make_params())
        pos = brackets._set_positions(pl.x_lines, D)
        self.assertEqual(pos[0], pl.x_lines[0])
        self.assertEqual(pos[-1], pl.x_lines[-1])
        gaps = [b - a for a, b in zip(pos, pos[1:])]
        for g in gaps:                                  # 攒档约 11 斗口
            self.assertLess(abs(g - 11 * D), 3 * D)

    def test_building_raises_eave_and_extends_projection(self):
        base = build_building_parts(make_params())[0]
        withb, pl = build_building_parts(make_params(bracket_set="五踩重昂"))
        self.assertEqual([c for c, _ in withb], ["platform", "columns", "beams", "red_wall", "wall_base", "joinery", "paper", "brackets", "roof"])
        roof0, roof1 = dict(base)["roof"], dict(withb)["roof"]
        (_, y0min, z0min), _ = roof0.bounds()
        (_, y1min, z1min), _ = roof1.bounds()
        self.assertAlmostEqual(z1min - z0min, 10 * D)    # 檐口抬高一个斗拱层
        self.assertAlmostEqual(y0min - y1min, 6 * D)     # 上檐出加出踩
        self.assertEqual(dict(base)["platform"].vertices, dict(withb)["platform"].vertices)  # 台基不变

    def test_validation(self):
        with self.assertRaises(ValueError):
            make_params(bracket_set="斗拱").validate()
        with self.assertRaises(ValueError):
            make_xiaoshi(bracket_set="三踩").validate()


class ColumnTests(unittest.TestCase):
    def test_columns_mesh(self):
        pl = plan.build_plan(make_params())
        m = columns.build_columns(pl, 112.0)
        m.validate()
        (_, _, zmin), (_, _, zmax) = m.bounds()
        self.assertAlmostEqual(zmin, 112.0)                       # 础坐台基顶
        self.assertAlmostEqual(zmax, 112.0 + 60 * D)              # 檐柱高 60D
        # 32 根柱（20 檐 + 12 金），每根柱础 + 柱身两个圆柱，各 2×16 顶点
        n_total = len(plan.eave_columns(pl)) + len(plan.gold_columns(pl))
        self.assertEqual(len(m.vertices), n_total * 2 * 32)

    def test_eave_column_diameter(self):
        pl = plan.build_plan(make_params())
        m = columns.build_columns(pl, 112.0)
        # 找一根前檐角柱（x = −L/2, y = −W/2），其柱身顶环直径应为 6D
        xs, ys, zs = zip(*m.vertices)
        target = (-pl.length / 2.0, -pl.width / 2.0)
        ring = [
            (x, y) for (x, y, z) in m.vertices
            if abs(z - (112.0 + 60 * D)) < 1e-6
            and abs(x - target[0]) < columns.CYLINDER_SEGMENTS * 2
            and abs(y - target[1]) < columns.CYLINDER_SEGMENTS * 2
        ]
        self.assertEqual(len(ring), 16)
        diameter = max(x for x, _ in ring) - min(x for x, _ in ring)
        self.assertAlmostEqual(diameter, 6 * D, places=6)


class RoofTests(unittest.TestCase):
    def setUp(self):
        self.pl = plan.build_plan(make_params())
        self.z_base = 112.0 + 60 * D  # 台基顶 + 柱高（S-002）
        self.m = roof.build_roof_xieshan(self.pl, self.z_base)

    def test_mesh_valid_and_counts(self):
        self.m.validate()
        # 顶点：主坡 20 + 右端件 13×2 + 四角 4×3 + 正脊 8（含设计上的重合顶点）
        self.assertEqual(len(self.m.vertices), 66)
        # 面：主坡 8 + 两端各 4 + 四角 4 + 正脊 6
        self.assertEqual(len(self.m.faces), 26)

    def test_outline_and_height(self):
        (_, _, _), (xmax, ymax, zmax) = self.m.bounds()
        half = self.pl.eave_width / 2.0
        l2e = self.pl.eave_length / 2.0
        s1 = (half / D) / 4 * D            # 一步架水平深（均分 4 步，S-003）
        ridge_z = (half / D) / 4 * (0.5 + 0.65 + 0.75 + 0.9) * D
        self.assertAlmostEqual(xmax, l2e)                 # 撒头檐口到达山面檐口线
        self.assertAlmostEqual(ymax, half)
        self.assertAlmostEqual(zmax, self.z_base + ridge_z + 2 * D)  # 脊顶 = 脊 + 脊截面高
        # 脊端内收一步架（S-005）：脊标高处 |x| 最大值 = 正脊半长
        at_ridge = [
            (x, y) for (x, y, z) in self.m.vertices
            if abs(z - (self.z_base + ridge_z)) < 1e-6
        ]
        self.assertTrue(at_ridge)
        self.assertAlmostEqual(max(abs(x) for x, _ in at_ridge), l2e - s1)

    def test_symmetry(self):
        # 关于 X 轴、Y 轴均对称（顶点镜像成对出现）
        for axis in (0, 1):
            keys = set()
            for v in self.m.vertices:
                w = list(v)
                w[axis] = -w[axis]
                keys.add((round(w[0], 6), round(w[1], 6), round(w[2], 6)))
            for v in self.m.vertices:
                self.assertIn(
                    (round(v[0], 6), round(v[1], 6), round(v[2], 6)), keys,
                    f"屋顶在第 {axis} 轴上不对称",
                )


class SingleBayTests(unittest.TestCase):
    """1×1 模块（万方安和接间）：单间殿合法可建，无金柱。"""

    def test_one_bay_module(self):
        p = config.BuildingParams(
            id="s", name="s", doukou_cun=2.5, bays=1, depth_bays=1,
            bay_brackets=3, depth_brackets=3,
        )
        pl = plan.build_plan(p)
        self.assertEqual(len(pl.bay_widths), 1)
        self.assertAlmostEqual(pl.bay_widths[0], (11 * 3 + 1) * 8.0, places=6)
        self.assertEqual(plan.gold_columns(pl), [])  # 单间无内柱
        self.assertEqual(len(plan.eave_columns(pl)), 4)
        m = columns.build_columns(pl, 64.0)
        m.validate()
        self.assertEqual(len(m.vertices), 4 * 2 * 32)


class MeshPrimitiveTests(unittest.TestCase):
    def test_box(self):
        m = mesh.box(10.0, 20.0, 0.0, 5.0)
        m.validate()
        self.assertEqual((len(m.vertices), len(m.faces)), (8, 6))

    def test_cylinder(self):
        m = mesh.cylinder(0.0, 10.0, 5.0, segments=16)
        m.validate()
        self.assertEqual(len(m.vertices), 32)
        self.assertEqual(len(m.faces), 16 + 2)

    def test_merged_and_mirrored(self):
        a = mesh.box(10, 10, 0, 1)
        b = mesh.cylinder(0, 1, 2)
        c = a.merged(b)
        self.assertEqual(len(c.vertices), len(a.vertices) + len(b.vertices))
        mx = c.mirrored("x")
        self.assertEqual(len(mx.faces), len(c.faces))
        my = c.mirrored("y")
        self.assertEqual(len(my.faces), len(c.faces))


if __name__ == "__main__":
    unittest.main()
