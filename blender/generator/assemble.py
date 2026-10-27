"""assemble.py — 组装单体建筑（仅 Blender 内运行）。

用法（``--`` 之后为脚本参数）：

    blender --background --python blender/generator/assemble.py -- \
        --config data/buildings/example_xieshan.yaml \
        --out build/zhengda_guangming.glb --clear

流程：读 YAML → 纯函数几何（plan / platform / columns / roof）→ bpy 建网格 →
按场景单位 1 单位 = 1 cm 设置（ADR-0001，glTF 导出时由导出器换算为米）→
可选导出 glTF/glb → 打印统计。

预期效果：单一集合内 3 个对象——
- 台基（长方体，Z 0 → 台基高）
- 柱网（檐柱 / 金柱 / 柱础，圆柱近似）
- 屋顶（按 roof 类型：歇山 / 庑殿 / 攒尖 / 硬山 / 悬山，简化，见 roof.py）
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PKG_PARENT = Path(__file__).resolve().parents[1]
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))

import dataclasses

from generator import brackets as brackets_mod
from generator import carpentry as carpentry_mod
from generator import columns as columns_mod
from generator import config as config_mod
from generator import plan as plan_mod
from generator import platform as platform_mod
from generator import roof as roof_mod


BUILDING_COMPONENTS = ("platform", "columns", "roof")   # 台基 / 柱网 / 屋顶（网格标签用英文）
BRACKETS_COMPONENT = "brackets"                          # 斗拱层（仅 bracket_set 给定时生成）


def build_building_meshes(p: config_mod.BuildingParams):
    """纯几何部分（无 bpy）：返回 (台基, 柱网, 屋顶, 平面几何)。供测试复用；不含斗拱层。"""
    parts, pl = build_building_parts(p)
    d = dict(parts)
    return d["platform"], d["columns"], d["roof"], pl


def build_building_parts(p: config_mod.BuildingParams):
    """纯几何部分（无 bpy）：返回 ([(构件 id, Mesh)], 平面几何)。

    构件依次为 platform / columns / 檐枋墙体装修（carpentry.COMPONENTS，按 enclosure）/
    [brackets] / roof。有斗拱时（S-002 修正，S-040）：
    檐口抬高一个斗拱层，上檐出加斗拱出踩；台基与柱高不变。
    """
    pl = plan_mod.build_plan(p)
    stories = max(1, int(getattr(p, "stories", 1)))
    m_platform = platform_mod.build_platform(pl, p.platform_height_cm, p)
    m_columns = columns_mod.build_columns(pl, p.platform_height_cm, stories)
    col_h = columns_mod.eave_column_height_cm(pl)
    column_top = p.platform_height_cm + col_h * stories
    z_base = column_top
    roof_plan = pl
    m_brackets = None
    if p.bracket_set:
        tiao = brackets_mod.tiao_count(p.bracket_set)
        m_brackets = brackets_mod.build_brackets(pl, column_top, tiao)
        z_base += brackets_mod.layer_height_cm(pl.doukou_cm, tiao)
        roof_plan = dataclasses.replace(
            pl, upper_eave_cm=pl.upper_eave_cm + brackets_mod.projection_cm(pl.doukou_cm, tiao)
        )
    skirts: list[float] = []
    if getattr(p, "double_eave", False):
        skirts.append(p.platform_height_cm + col_h)          # 重檐下檐：檐柱顶
    if stories >= 2:
        skirts.append(p.platform_height_cm + col_h * (stories - 1))  # 楼腰檐
    m_roof = roof_mod.build_roof(
        roof_plan, z_base, p.roof, skirts=tuple(sorted(set(skirts))),
        wall_base_cm=p.platform_height_cm,   # 硬山山墙自台基顶砌起
    )
    parts = [("platform", m_platform), ("columns", m_columns)]
    parts += carpentry_mod.build_enclosure(
        pl, p.platform_height_cm, stories,
        enclosure=p.enclosure, corridor=p.corridor, gable_walls="硬山" in p.roof,
    )
    if m_brackets is not None:
        parts.append((BRACKETS_COMPONENT, m_brackets))
    parts.append(("roof", m_roof))
    return parts, pl


def add_mesh_object(name: str, m, collection):
    """bpy：由纯数据网格创建对象并挂入集合。"""
    import bpy

    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in m.vertices], [], [tuple(f) for f in m.faces])
    me.validate(verbose=False)
    me.update()
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    return ob


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(description="圆明园 · 清式建筑最小生成器（Blender 入口）")
    ap.add_argument("--config", required=True, help="建筑参数 YAML 路径")
    ap.add_argument("--out", default=None, help="导出 glb / gltf 路径（可选）")
    ap.add_argument("--clear", action="store_true", help="以空场景开始")
    args = ap.parse_args(argv)

    p = config_mod.load_building(args.config)
    parts, pl = build_building_parts(p)
    for _comp, m in parts:
        m.validate()
    meshes = dict(parts)
    m_platform, m_roof = meshes["platform"], meshes["roof"]

    import bpy  # noqa: PLC0415 —— 仅在 Blender 内导入

    if args.clear:
        bpy.ops.wm.read_factory_settings(use_empty=True)

    # 场景单位：1 unit = 1 cm（ADR-0001）。glTF 以米计，导出器按场景单位自动换算。
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 0.01

    coll = bpy.data.collections.new(f"BUILD_{p.id}")
    scene.collection.children.link(coll)
    for comp, m in parts:
        add_mesh_object(f"{p.id}_{comp}", m, coll)

    (_, _, zmin), (_, _, zmax) = m_roof.bounds()
    (pxmin, pymin, _), (pxmax, pymax, _) = m_platform.bounds()
    module = "斗口" if p.grade == "大式" else "等效模数"
    print(f"[assemble] 建筑: {p.name}（{p.id}，{p.grade}，{module} {pl.doukou_cm:.2f} cm，"
          f"檐柱高 {pl.column_height_cm:.1f} cm / 径 {pl.eave_column_diameter_cm:.1f} cm）")
    print(f"[assemble] 台明外包: {pxmax - pxmin:.1f} × {pymax - pymin:.1f} cm；"
          f"脊顶标高 ≈ {zmax:.1f} cm（檐口 {zmin:.1f} cm）")
    print(f"[assemble] 柱网: 檐柱 {len(plan_mod.eave_columns(pl))} 根 + "
          f"金柱 {len(plan_mod.gold_columns(pl))} 根")
    print(f"[assemble] 对象 {len(parts)} 个，顶点共 "
          f"{sum(len(m.vertices) for _c, m in parts)} 个")

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        fmt = "GLB" if out.suffix.lower() == ".glb" else "GLTF_SEPARATE"
        bpy.ops.export_scene.gltf(filepath=str(out), export_format=fmt)
        print(f"[assemble] 已导出: {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
