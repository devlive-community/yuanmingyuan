"""test_config.py — YAML 读取（PyYAML / 极简解析器回退）与参数校验。"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))

from generator import config  # noqa: E402

SAMPLE = """\
# 注释行
building:
  id: zhengda_guangming
  name: 正大光明殿
  grade: 大式
  doukou_grade: 7      # 七等斗口
  doukou_cun: 3.0
  bays: 7
  depth_bays: 3
  bay_brackets: 6
  depth_brackets: 4
  roof: 歇山
  platform_height_chi: 3.5
  evidence:
    - source: 占位示例：样式雷图档（编号待补）
      confidence: placeholder
    - source: 推测：参照同期同等级大式殿宇
      confidence: low
"""


class MiniYamlTests(unittest.TestCase):
    def test_parse_sample(self):
        data = config._mini_yaml_load(SAMPLE)
        b = data["building"]
        self.assertEqual(b["id"], "zhengda_guangming")
        self.assertEqual(b["name"], "正大光明殿")
        self.assertEqual(b["grade"], "大式")
        self.assertEqual(b["doukou_grade"], 7)
        self.assertAlmostEqual(b["doukou_cun"], 3.0)
        self.assertEqual(b["bays"], 7)
        self.assertEqual(b["roof"], "歇山")
        self.assertAlmostEqual(b["platform_height_chi"], 3.5)
        self.assertEqual(
            b["evidence"],
            [
                {"source": "占位示例：样式雷图档（编号待补）", "confidence": "placeholder"},
                {"source": "推测：参照同期同等级大式殿宇", "confidence": "low"},
            ],
        )

    def test_string_list(self):
        data = config._mini_yaml_load("tags:\n  - a\n  - b\n")
        self.assertEqual(data["tags"], ["a", "b"])

    def test_matches_pyyaml_when_available(self):
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError:
            self.skipTest("环境未安装 PyYAML，跳过一致性对比")
        self.assertEqual(config._mini_yaml_load(SAMPLE), yaml.safe_load(SAMPLE))


class LoadBuildingTests(unittest.TestCase):
    def _write(self, text: str) -> str:
        f = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8")
        f.write(text)
        f.close()
        self.addCleanup(Path(f.name).unlink)
        return f.name

    def test_load_sample(self):
        p = config.load_building(self._write(SAMPLE))
        self.assertEqual(p.id, "zhengda_guangming")
        self.assertEqual(p.name, "正大光明殿")
        self.assertAlmostEqual(p.doukou_cm, 3.0 * 3.2)
        self.assertAlmostEqual(p.platform_height_cm, 3.5 * 32.0)
        self.assertEqual(len(p.evidence), 2)
        self.assertEqual(p.evidence[0]["confidence"], "placeholder")

    def test_doukou_cun_takes_priority(self):
        p = config.load_building(self._write(SAMPLE))
        self.assertAlmostEqual(p.doukou_cm, 9.6)  # cun 3.0，而非 grade 7 的同值冲突检验
        p2 = config.BuildingParams(id="x", name="x", doukou_grade=1)
        self.assertAlmostEqual(p2.doukou_cm, 6.0 * 3.2)

    def test_round_roof_and_moon_platform_fields(self):
        text = SAMPLE.replace(
            "  roof: 歇山",
            "  roof: 卷棚歇山\n  moon_platform: true\n  stairs_flights: 3\n  stairs_steps: 9",
        )
        p = config.load_building(self._write(text))
        self.assertEqual(p.roof, "卷棚歇山")
        self.assertTrue(p.moon_platform)
        self.assertEqual(p.stairs_flights, 3)
        self.assertEqual(p.stairs_steps, 9)

    def test_xiaoshi_fields(self):
        text = (
            "building:\n  id: t\n  name: 小式轩\n  grade: 小式\n  bays: 3\n  depth_bays: 1\n"
            "  ming_bay_chi: 10.5\n  side_bay_chi: 9\n  depth_bay_chi: 12\n  roof: 卷棚硬山\n"
        )
        p = config.load_building(self._write(text))
        self.assertEqual(p.grade, "小式")
        self.assertAlmostEqual(p.ming_bay_chi, 10.5)
        self.assertAlmostEqual(p.side_bay_chi, 9.0)
        self.assertAlmostEqual(p.depth_bay_chi, 12.0)
        self.assertEqual(config._mini_yaml_load(text)["building"]["ming_bay_chi"], 10.5)

    def test_unknown_field_rejected(self):
        text = SAMPLE.replace("  roof: 歇山", "  roof: 歇山\n  bogus: 1")
        with self.assertRaises(ValueError):
            config.load_building(self._write(text))

    def test_missing_building_section(self):
        with self.assertRaises(ValueError):
            config.load_building(self._write("foo: 1\n"))

    def test_validation_rules(self):
        with self.assertRaises(ValueError):  # 面阔须为奇数
            config.BuildingParams(id="x", name="x", doukou_cun=3.0, bays=6).validate()
        with self.assertRaises(ValueError):  # 未支持的屋顶类型（盝顶）
            config.BuildingParams(id="x", name="x", doukou_cun=3.0, roof="盝顶").validate()
        for r in ("庑殿", "攒尖", "硬山", "卷棚硬山", "悬山", "卷棚悬山"):
            config.BuildingParams(id="x", name="x", doukou_cun=3.0, roof=r).validate()
        with self.assertRaises(ValueError):  # 须提供斗口
            config.BuildingParams(id="x", name="x").doukou_cm
        with self.assertRaises(ValueError):  # 进深须 ≥1
            config.BuildingParams(id="x", name="x", doukou_cun=3.0, depth_bays=0).validate()
        # 1×1 模块（万方安和接间）合法可建
        p1 = config.BuildingParams(
            id="s", name="s", doukou_cun=2.5, bays=1, depth_bays=1,
            bay_brackets=3, depth_brackets=3,
        )
        p1.validate()


if __name__ == "__main__":
    unittest.main()
