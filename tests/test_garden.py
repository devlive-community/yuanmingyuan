"""test_garden.py — 总园装配单测：解析、方位关系、湖面与导出。"""

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "blender"))

from generator import config, gltf, scene  # noqa: E402

GARDEN_PATH = _ROOT / "data" / "gardens" / "yuanmingyuan_preview.yaml"


class GardenLoadTests(unittest.TestCase):
    def test_load(self):
        g = config.load_garden(GARDEN_PATH)
        self.assertEqual(g.id, "yuanmingyuan_preview")
        self.assertEqual(len(g.scenes), 5)  # 含方壶胜境
        self.assertEqual(len(g.lakes), 3)  # 前湖/后湖/福海（多边形）
        self.assertEqual([lk.name for lk in g.lakes], ["前湖", "后湖", "福海"])

    def test_garden_unknown_field_rejected(self):
        text = GARDEN_PATH.read_text(encoding="utf-8").replace(
            "  water: true", "  water: true\n  bogus: 1"
        )
        # 本文件无 water 字段时该替换不生效；改用确定存在的行
        text = GARDEN_PATH.read_text(encoding="utf-8").replace(
            "  id: yuanmingyuan_preview", "  id: yuanmingyuan_preview\n  bogus: 1"
        )
        p = _ROOT / "build" / "_bad_garden.yaml"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        try:
            with self.assertRaises(ValueError):
                config.load_garden(p)
        finally:
            p.unlink()


class GardenBuildTests(unittest.TestCase):
    def setUp(self):
        self.garden = config.load_garden(GARDEN_PATH)
        self.parts = dict(scene.build_garden(self.garden, GARDEN_PATH))

    def test_labels_and_counts(self):
        self.assertEqual(len(self.parts), 177)  # 五景（方壶含景内水面）+ 三湖（含福海），含檐枋墙体装修（S-042）
        self.assertIn("zhengda_guangming/zhengda_guangming/platform", self.parts)
        self.assertIn("wanfang_anhe/wanfang_wing/roof", self.parts)
        self.assertIn("lake_1/water", self.parts)
        self.assertIn("lake_2/water", self.parts)   # 后湖
        self.assertIn("fuhai/water", self.parts)

    def test_qinzheng_east_of_zhengda(self):
        (x0, _, _), (x1, _, _) = self.parts["zhengda_guangming/zhengda_guangming/platform"].bounds()
        (qx0, _, _), (qx1, _, _) = self.parts["qinzheng_qinxian/qinzheng_qinxian_dian/platform"].bounds()
        self.assertGreater(qx0, x1)  # 勤政亲贤整体在主殿之东

    def test_jiuzhou_north_of_zhengda(self):
        (_, _, _), (_, y1, _) = self.parts["zhengda_guangming/zhengda_guangming/platform"].bounds()
        (_, jy0, _), (_, _, _) = self.parts["jiuzhou_qingyan/yuanmingyuan_dian/platform"].bounds()
        self.assertGreater(jy0, y1)  # 九洲清晏在主殿之北（+Y）

    def test_lakes(self):
        for key in ("lake_1", "lake_2"):   # 前湖 / 后湖
            (_, _, z0), (_, _, z1) = self.parts[f"{key}/water"].bounds()
            self.assertAlmostEqual(z0, -30.0)
            self.assertAlmostEqual(z1, 0.6)  # 略高于景内水面，避免共面闪烁

    def test_garden_glb_parses(self):
        prims = [gltf.Primitive(name, m, (0.5, 0.5, 0.5)) for name, m in self.parts.items()]
        blob = gltf.build_glb(prims)
        version, doc, _ = gltf.parse_glb(blob)
        self.assertEqual(version, 2)
        self.assertEqual(len(doc["nodes"]), len(self.parts))


SANYUAN_GARDEN = _ROOT / "data" / "gardens" / "sanyuan_preview.yaml"


class SanyuanGardenTests(unittest.TestCase):
    """圆明三园预览：嵌套总园（圆明园）＋长春园含经堂＋绮春园正觉寺。"""

    def test_nested_recursion(self):
        g = config.load_garden(SANYUAN_GARDEN)
        self.assertEqual([s.ref for s in g.scenes],
                         ["yuanmingyuan_preview.yaml", "../scenes/hanjingtang.yaml", "../scenes/zhengjuesi.yaml"])
        parts = dict(scene.build_garden(g, SANYUAN_GARDEN))
        # 圆明园子园 78（五景三湖，方壶含景内水面，正大光明主殿含斗拱层）＋ 含经堂 9 ＋ 正觉寺 9
        self.assertEqual(len(parts), 225)  # 含檐枋墙体装修（S-042）
        self.assertIn("yuanmingyuan_preview/zhengda_guangming/zhengda_guangming/platform", parts)
        self.assertIn("hanjingtang/hanjingtang_dian/platform", parts)
        self.assertIn("zhengjuesi/zhengjuesi_sanshengdian/roof", parts)

    def test_sangyuan_layout_relations(self):
        parts = dict(scene.build_garden(config.load_garden(SANYUAN_GARDEN), SANYUAN_GARDEN))
        (_, yy0, _), (_, _, _) = parts["yuanmingyuan_preview/zhengda_guangming/zhengda_guangming/platform"].bounds()
        (_, cy0, _), (_, _, _) = parts["hanjingtang/hanjingtang_dian/platform"].bounds()
        (_, zy0, _), (_, _, _) = parts["zhengjuesi/zhengjuesi_shanmen/platform"].bounds()
        self.assertGreater(cy0, yy0)   # 长春园含经堂在北（示意，北 = +Y）
        self.assertLess(zy0, yy0)    # 绮春园正觉寺在南（示意，南 = −Y）


if __name__ == "__main__":
    unittest.main()
