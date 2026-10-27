"""test_scene.py — 景群装配单测：网格旋转、场景解析、方位与导出。"""

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "blender"))

from generator import config, gltf, mesh, plan, roof, scene  # noqa: E402

SCENE_PATH = _ROOT / "data" / "scenes" / "zhengda_guangming.yaml"


def platform_of(parts, scene_obj, scene_path, role):
    """按 YAML 角色名取该栋台基网格（网格标签为英文 key，见 scene.building_keys）。"""
    keys = {sb.role: key for key, sb, _ in scene.building_keys(scene_obj, scene_path)}
    return parts[f"{keys[role]}/platform"]


class RotateMeshTests(unittest.TestCase):
    def test_rotate_90_swaps_extents(self):
        m = mesh.box(10.0, 20.0, 0.0, 5.0)  # x 10, y 20
        r = m.rotated_z(90.0)
        r.validate()
        (xmin, ymin, _), (xmax, ymax, _) = r.bounds()
        self.assertAlmostEqual(xmax - xmin, 20.0, places=6)  # 长边转到 X
        self.assertAlmostEqual(ymax - ymin, 10.0, places=6)

    def test_rotate_360_identity(self):
        m = mesh.box(10.0, 20.0, 0.0, 5.0)
        r = m.rotated_z(360.0)
        for a, b in zip(m.vertices, r.vertices):
            for u, v in zip(a, b):
                self.assertAlmostEqual(u, v, places=6)


class SceneLoadTests(unittest.TestCase):
    def test_load_real_scene(self):
        s = config.load_scene(SCENE_PATH)
        self.assertEqual(s.id, "zhengda_guangming")
        self.assertEqual(s.name, "正大光明")
        self.assertEqual(len(s.buildings), 4)
        roles = [b.role for b in s.buildings]
        self.assertEqual(roles, ["主殿", "西配殿", "东配殿", "出入贤良门"])
        self.assertEqual(s.buildings[1].rotation_deg, 90.0)
        self.assertEqual(s.buildings[2].rotation_deg, 270.0)  # -90 归一化
        self.assertAlmostEqual(s.buildings[3].y_cm, -2974.0)

    def test_reject_bad_rotation(self):
        text = SCENE_PATH.read_text(encoding="utf-8").replace(
            "rotation_deg: 90", "rotation_deg: 45"
        )
        p = _ROOT / "build" / "_bad_scene.yaml"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        try:
            with self.assertRaises(ValueError):
                config.load_scene(p)
        finally:
            p.unlink()


class SceneBuildTests(unittest.TestCase):
    def setUp(self):
        self.scene = config.load_scene(SCENE_PATH)
        self.parts = scene.build_scene(self.scene, SCENE_PATH)

    def test_component_count(self):
        self.assertEqual(len(self.parts), 4 * 8 + 1)  # 4 栋 ×（3 构件 + 5 类檐枋墙体装修）+ 主殿斗拱层（S-040）
        labels = [name for name, _ in self.parts]
        self.assertIn("zhengda_guangming/brackets", labels)
        self.assertIn("zhengda_guangming/platform", labels)
        self.assertIn("churu_xianliang_men/roof", labels)

    def test_west_peidian_rotation_and_position(self):
        name, m = next(x for x in self.parts if x[0] == "peidian_wuying/platform")
        m.validate()
        (xmin, ymin, _), (xmax, ymax, _) = m.bounds()
        d = 9.6  # noqa: F841 —— 主殿斗口；配殿斗口为 2.5 寸 = 8.0 cm
        pd = 8.0
        # 配殿五楹面阔 = 45D + 4×34D = 181D；台基外包再加两侧上檐出 2×21D → 223D，旋转后沿 Y
        self.assertAlmostEqual(ymax - ymin, (181 + 42) * pd, places=4)
        # 进深 2 间 × 34D = 68D，台基外包 → 110D，旋转后沿 X
        self.assertAlmostEqual(xmax - xmin, (68 + 42) * pd, places=4)
        # 中心 x = −2860
        self.assertAlmostEqual((xmin + xmax) / 2.0, -2860.0, places=4)

    def test_gate_south_of_main_hall(self):
        _, m_gate = next(x for x in self.parts if x[0] == "churu_xianliang_men/platform")
        (_, ymin_gate, _), (_, ymax_gate, _) = m_gate.bounds()
        _, m_main = next(x for x in self.parts if x[0] == "zhengda_guangming/platform")
        (_, ymin_main, _), (_, ymax_main, _) = m_main.bounds()
        self.assertLess(ymax_gate, ymin_main)  # 门殿整体在主殿之南（−Y）
        self.assertAlmostEqual((ymin_gate + ymax_gate) / 2.0, -2974.0, places=4)

    def test_scene_glb_parses(self):
        prims = [
            gltf.Primitive(name, m, (0.5, 0.5, 0.5)) for name, m in self.parts
        ]
        blob = gltf.build_glb(prims)
        version, doc, _ = gltf.parse_glb(blob)
        self.assertEqual(version, 2)
        self.assertEqual(len(doc["nodes"]), 33)
        self.assertEqual(len(doc["meshes"]), 33)


JIUZHOU_SCENE = _ROOT / "data" / "scenes" / "jiuzhou_qingyan.yaml"


class JiuzhouQingyanSceneTests(unittest.TestCase):
    """九洲清晏：中轴三殿自南向北（圆明园殿 → 奉三无私殿 → 九洲清晏殿）。"""

    def test_roles_and_order(self):
        s = config.load_scene(JIUZHOU_SCENE)
        self.assertEqual(
            [b.role for b in s.buildings], ["圆明园殿", "奉三无私殿", "九洲清晏殿"]
        )
        parts = dict(scene.build_scene(s, JIUZHOU_SCENE))
        spans = {}
        for role in ("圆明园殿", "奉三无私殿", "九洲清晏殿"):
            (_, y0, _), (_, y1, _) = platform_of(parts, s, JIUZHOU_SCENE, role).bounds()
            spans[role] = (y0, y1)
        # 自南（小 y）向北（大 y）依次不重叠
        self.assertLess(spans["圆明园殿"][1], spans["奉三无私殿"][0])
        self.assertLess(spans["奉三无私殿"][1], spans["九洲清晏殿"][0])

    def test_bay_counts_from_data(self):
        for name, bays in (("yuanmingyuan_dian", 5), ("fengsanwusi_dian", 7), ("jiuzhou_qingyan_dian", 7)):
            p = config.load_building(_ROOT / "data" / "buildings" / f"{name}.yaml")
            self.assertEqual(p.bays, bays)


WANFANG_SCENE = _ROOT / "data" / "scenes" / "wanfang_anhe.yaml"


class WanfangAnheSceneTests(unittest.TestCase):
    """万方安和：卍形 9 模块拼合（中心 3×3＋接间 1×1×4＋支路 5×1×4＝33 间）＋示意水面。"""

    def setUp(self):
        self.scene = config.load_scene(WANFANG_SCENE)
        self.parts = dict(scene.build_scene(self.scene, WANFANG_SCENE))

    def test_modules_and_water_first(self):
        self.assertEqual(len(self.scene.buildings), 9)
        self.assertTrue(self.scene.water)
        self.assertEqual(list(self.parts)[0], "water")
        self.assertEqual(len(self.parts), 9 * 7 + 1)  # 四面装修无红墙上身（S-042）

    def test_butt_joints(self):
        # 接间台基与中心殿台基边缘相接（gap 0，无面积重叠）
        (_, ymin_stub, _), (_, _, _) = self.parts["wanfang_stub/platform"].bounds()
        (_, _, _), (_, ymax_center, _) = self.parts["wanfang_center/platform"].bounds()
        self.assertAlmostEqual(ymin_stub, ymax_center, places=4)

    def test_wing_rotation(self):
        (xmin, ymin, _), (xmax, ymax, _) = self.parts["wanfang_wing/platform"].bounds()
        self.assertAlmostEqual(xmax - xmin, 608.0, places=4)   # 进深向（272＋2×168）
        self.assertAlmostEqual(ymax - ymin, 1784.0, places=4)  # 面阔向（1448＋2×168），旋转后沿 Y

    def test_water_covers_buildings(self):
        (wx0, wy0, wz0), (wx1, wy1, wz1) = self.parts["water"].bounds()
        self.assertAlmostEqual(wz0, -30.0)
        self.assertAlmostEqual(wz1, 0.0)
        for role in ("中心殿", "北支路", "东支路", "南支路", "西支路"):
            (bx0, by0, _), (bx1, by1, _) = platform_of(self.parts, self.scene, WANFANG_SCENE, role).bounds()
            self.assertGreaterEqual(bx0, wx0)
            self.assertLessEqual(bx1, wx1)
            self.assertGreaterEqual(by0, wy0)
            self.assertLessEqual(by1, wy1)


HANJINGTANG_SCENE = _ROOT / "data" / "scenes" / "hanjingtang.yaml"


class HanjingtangSceneTests(unittest.TestCase):
    """含经堂（长春园）：中轴三殿南→北（含经堂 → 蕴真斋 → 淳化轩）。"""

    def test_roles_and_order(self):
        s = config.load_scene(HANJINGTANG_SCENE)
        self.assertEqual(
            [b.role for b in s.buildings], ["含经堂", "蕴真斋", "淳化轩"]
        )
        parts = dict(scene.build_scene(s, HANJINGTANG_SCENE))
        spans = {}
        for role in ("含经堂", "蕴真斋", "淳化轩"):
            (_, y0, _), (_, y1, _) = platform_of(parts, s, HANJINGTANG_SCENE, role).bounds()
            spans[role] = (y0, y1)
        self.assertLess(spans["含经堂"][1], spans["蕴真斋"][0])
        self.assertLess(spans["蕴真斋"][1], spans["淳化轩"][0])

    def test_bay_counts_from_data(self):
        for name, bays in (("hanjingtang_dian", 7), ("yunzhen_zhai", 5), ("chunhua_xuan", 5)):
            p = config.load_building(_ROOT / "data" / "buildings" / f"{name}.yaml")
            self.assertEqual(p.bays, bays)


PENGDAO_SCENE = _ROOT / "data" / "scenes" / "pengdao_yaotai.yaml"


class PengdaoYaotaiSceneTests(unittest.TestCase):
    """蓬岛瑶台（福海中央主岛）：宫门(3间)→正殿(7间)，东列畅襟楼、西列神洲三岛。"""

    def setUp(self):
        self.scene = config.load_scene(PENGDAO_SCENE)
        self.parts = dict(scene.build_scene(self.scene, PENGDAO_SCENE))

    def test_roles_and_island(self):
        self.assertEqual(
            [b.role for b in self.scene.buildings],
            ["宫门", "正殿", "随安室", "日日平安报好音", "畅襟楼", "神洲三岛"],
        )
        self.assertEqual(len(self.parts), 6 * 8 + 1)  # 6 栋 ×（3 构件 + 5 类檐枋墙体装修）+ 岛台
        self.assertEqual(list(self.parts)[0], "island")
        (_, _, z0), (_, _, z1) = self.parts["island"].bounds()
        self.assertAlmostEqual(z0, 0.0)
        self.assertAlmostEqual(z1, 30.0)  # 高于总园湖面 0.6

    def test_island_covers_buildings(self):
        (ix0, iy0, _), (ix1, iy1, _) = self.parts["island"].bounds()
        for role in ("宫门", "正殿", "畅襟楼"):
            (bx0, by0, _), (bx1, by1, _) = platform_of(self.parts, self.scene, PENGDAO_SCENE, role).bounds()
            self.assertGreaterEqual(bx0, ix0)
            self.assertLessEqual(bx1, ix1)
            self.assertGreaterEqual(by0, iy0)
            self.assertLessEqual(by1, iy1)

    def test_layout(self):
        (_, _, _), (_, gate_y1, _) = self.parts["pengdao_gongmen/platform"].bounds()
        (_, dian_y0, _), (_, _, _) = self.parts["pengdao_zhengdian/platform"].bounds()
        self.assertLess(gate_y1, dian_y0)  # 宫门在正殿之南
        (cx0, _, _), (_, _, _) = self.parts["pengdao_changjin_lou/platform"].bounds()
        (sx0, _, _), (sx1, _, _) = self.parts["pengdao_shenzhou/platform"].bounds()
        self.assertGreater(cx0, 0.0)   # 畅襟楼在东
        self.assertLess(sx1, 0.0)      # 神洲三岛在西

    def test_zhengdian_seven_bays(self):
        p = config.load_building(_ROOT / "data" / "buildings" / "pengdao_zhengdian.yaml")
        self.assertEqual(p.bays, 7)
        (x0, _, _), (x1, _, _) = self.parts["pengdao_zhengdian/platform"].bounds()
        # 七楹 403D ＋ 上檐出 42D ＝ 445D × 8 cm = 3560
        self.assertAlmostEqual(x1 - x0, 3560.0, places=4)


ZHENGJUESI_SCENE = _ROOT / "data" / "scenes" / "zhengjuesi.yaml"


class ZhengjuesiSceneTests(unittest.TestCase):
    """正觉寺（绮春园）：山门 → 天王殿 → 三圣殿（七间三进深）。"""

    def test_roles_and_order(self):
        s = config.load_scene(ZHENGJUESI_SCENE)
        self.assertEqual(
            [b.role for b in s.buildings], ["山门", "天王殿", "三圣殿"]
        )
        parts = dict(scene.build_scene(s, ZHENGJUESI_SCENE))
        spans = {}
        for role in ("山门", "天王殿", "三圣殿"):
            (_, y0, _), (_, y1, _) = platform_of(parts, s, ZHENGJUESI_SCENE, role).bounds()
            spans[role] = (y0, y1)
        self.assertLess(spans["山门"][1], spans["天王殿"][0])
        self.assertLess(spans["天王殿"][1], spans["三圣殿"][0])

    def test_sanshengdian_seven_bays(self):
        p = config.load_building(_ROOT / "data" / "buildings" / "zhengjuesi_sanshengdian.yaml")
        self.assertEqual(p.bays, 7)
        self.assertEqual(p.depth_bays, 3)
        s = config.load_scene(ZHENGJUESI_SCENE)
        parts = dict(scene.build_scene(s, ZHENGJUESI_SCENE))
        (x0, _, _), (x1, _, _) = parts["zhengjuesi_sanshengdian/platform"].bounds()
        # 七楹（403D）＋两侧上檐出（2×21D）＝ 445D × 8 cm = 3560
        self.assertAlmostEqual(x1 - x0, 3560.0, places=4)


FANGHU_SCENE = _ROOT / "data" / "scenes" / "fanghu_shengjing.yaml"


class FanghuSceneTests(unittest.TestCase):
    """方壶胜境：三重檐亭（山字形入湖）＋哕鸾殿＋琼华楼（二层）。"""

    def setUp(self):
        self.scene = config.load_scene(FANGHU_SCENE)
        self.parts = dict(scene.build_scene(self.scene, FANGHU_SCENE))

    def test_roles(self):
        self.assertEqual(
            [b.role for b in self.scene.buildings],
            ["哕鸾殿", "琼华楼", "迎薰亭", "集瑞亭", "凝祥亭"],
        )
        self.assertTrue(self.scene.water)

    def test_ting_has_skirt_eave(self):
        # 重檐亭：屋顶含腰檐环带（顶点比无腰檐多 8 个）
        ting = self.parts["fanghu_ting/roof"]
        ting.validate()
        pt = config.load_building(_ROOT / "data" / "buildings" / "fanghu_ting.yaml")
        pl = plan.build_plan(pt)
        z_base = pt.platform_height_cm + 480.0
        plain = roof.build_roof_xieshan(pl, z_base, style="卷棚歇山")
        self.assertEqual(len(ting.vertices), len(plain.vertices) + 8)

    def test_lou_two_stories(self):
        # 琼华楼柱通高两层：柱顶 z = 台基 64 + 2×480 = 1024
        (_, _, z0), (_, _, z1) = self.parts["fanghu_qionghua_lou/columns"].bounds()
        self.assertAlmostEqual(z0, 64.0, places=4)
        self.assertAlmostEqual(z1, 64.0 + 2 * 480.0, places=4)
        # 楼屋顶高于单层哕鸾殿屋顶
        (_, _, _), (_, _, lou_top) = self.parts["fanghu_qionghua_lou/roof"].bounds()
        (_, _, _), (_, _, dian_top) = self.parts["fanghu_kualun_dian/roof"].bounds()
        self.assertGreater(lou_top, dian_top)


QINZHENG_SCENE = _ROOT / "data" / "scenes" / "qinzheng_qinxian.yaml"


class QinzhengQinxianSceneTests(unittest.TestCase):
    """勤政亲贤：主殿（南）→ 抱厦（贴建）→ 保合太和九间殿（北）。"""

    def setUp(self):
        self.scene = config.load_scene(QINZHENG_SCENE)
        self.parts = dict(scene.build_scene(self.scene, QINZHENG_SCENE))

    def test_roles(self):
        self.assertEqual(
            [b.role for b in self.scene.buildings],
            ["勤政亲贤殿", "保合太和抱厦", "保合太和殿"],
        )

    def test_baoxia_abuts_baohetaihe(self):
        # 抱厦台基后缘与保合太和台基前缘相接（gap 0）
        (_, _, _), (_, y_baoxia, _) = self.parts["baohetaihe_baoxia/platform"].bounds()
        (_, y_main, _), (_, _, _) = self.parts["baohetaihe_dian/platform"].bounds()
        self.assertAlmostEqual(y_baoxia, y_main, places=4)

    def test_south_to_north_order(self):
        (_, _, _), (_, y_qinzheng, _) = self.parts["qinzheng_qinxian_dian/platform"].bounds()
        (_, y_baoxia_min, _), (_, _, _) = self.parts["baohetaihe_baoxia/platform"].bounds()
        self.assertLess(y_qinzheng, y_baoxia_min)
        # 九间殿台基外包 = 3328 + 2×168 = 3664
        (xmin, _, _), (xmax, _, _) = self.parts["baohetaihe_dian/platform"].bounds()
        self.assertAlmostEqual(xmax - xmin, 3664.0, places=4)


if __name__ == "__main__":
    unittest.main()
