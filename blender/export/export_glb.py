"""export_glb.py — 导出建筑或景群为 glTF 2.0 (.glb)。**无需 Blender**。

与 assemble.py（bpy 路径）共用同一纯函数几何层；本脚本可在任何装有
Python 3.9+ 的机器上直接运行，用于网页预览与快速核对。

用法（--config 与 --scene 二选一）：
    # 单栋建筑
    python3 blender/export/export_glb.py \
        --config data/buildings/zhengda_guangming.yaml \
        --out build/zhengda_guangming.glb

    # 景群（多栋，按方位摆放）
    python3 blender/export/export_glb.py \
        --scene data/scenes/zhengda_guangming.yaml \
        --out build/zhengda_guangming_scene.glb

浏览器查看请用 web/app（React 查看器，数据由 tools/export_web_data.py 导出）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[1]))  # blender/

from generator import config as config_mod  # noqa: E402
from generator import gltf as gltf_mod  # noqa: E402
from generator import scene as scene_mod  # noqa: E402
from generator.assemble import build_building_parts  # noqa: E402

# 占位材质颜色（线性 RGB 0–1）。仅用于在预览中区分构件；
# 屋顶灰瓦为**有据设色**（乾隆四十二年禁改黄瓦谕旨），但仍是纯色近似、无瓦面与彩画细节。
# 键为网格标签的末段（英文构件 id，见 generator.scene）。
PLACEHOLDER_COLORS = {
    "platform": (0.62, 0.60, 0.56),     # 台基：石材（白/灰大理石、花岗岩三说并存，仅取中性灰）
    "columns": (0.48, 0.10, 0.08),      # 柱网：朱红（清式油作通例，非本殿直接记载）
    "brackets": (0.16, 0.30, 0.30),     # 斗拱：青绿（清式彩画斗拱通例的近似，占位，S-040）
    "roof": (0.36, 0.37, 0.40),         # 屋顶：灰筒瓦（谕旨硬证，见 evidence）
    "beams": (0.14, 0.26, 0.30),        # 檐枋：青绿彩画通例的近似（占位，S-042）
    "red_wall": (0.55, 0.20, 0.15),     # 墙上身：红灰抹面（清官式通例，占位，S-042）
    "wall_base": (0.40, 0.40, 0.39),    # 下碱 / 槛墙：青砖（通例，占位，S-042）
    "joinery": (0.42, 0.09, 0.07),      # 槛框、槅扇、槛窗、板门：朱红油饰（通例，占位，S-042）
    "paper": (0.86, 0.82, 0.72),        # 窗户纸（高丽纸，占位，S-042）
    "water": (0.16, 0.28, 0.36),        # 水面：示意（非史料形体，S-021）
    "glazed_roof": (0.18, 0.44, 0.30),  # 绿琉璃瓦顶：孔雀绿琉璃瓦（人大清史文，medium）
    "island": (0.50, 0.48, 0.44),       # 岛台：湖心岛地面（示意，S-030）
    # 西洋楼（海晏堂 v3）：末段为材质类
    "walls": (0.80, 0.62, 0.58),        # 墙身：粉红色灰（维基「墙身抹粉红色灰」，medium）
    "recess": (0.23, 0.21, 0.18),       # 券洞内暗面（参考图效果版）
    "limestone": (0.80, 0.74, 0.62),    # 参考图效果版：米白石材（非史料，ADR-0003）
    "marble": (0.88, 0.87, 0.84),       # 汉白玉石作（立柱、栏杆、石梯、池壁）
    "windows": (0.13, 0.14, 0.16),      # 门窗暗面（占位）
    "cascade": (0.36, 0.52, 0.62),      # 导水台（跌水，占位）
    "tin": (0.55, 0.57, 0.60),          # 锡海锡板（占位）
    "bronze": (0.40, 0.28, 0.16),       # 生肖兽首铜质（medium）
    "paving": (0.62, 0.60, 0.56),       # 广场铺地（占位）
    "glazed_ridge": (0.80, 0.62, 0.20), # 黄琉璃脊（「脊桶为黄琉璃」，人大清史文，medium）
    "leaves": (0.26, 0.40, 0.18),       # 叶片卡树冠（参考图效果版，布景）
    "foliage": (0.24, 0.36, 0.18),      # 修剪树冠（示意）
    "bark": (0.36, 0.27, 0.19),         # 树干（示意）
    "jet": (0.85, 0.92, 0.95),          # 喷水标记（查看器隐藏，按两端生成水柱）
    "gold_roof": (0.72, 0.58, 0.26),    # 远瀛观第二层鱼鳞金瓦（维基，medium）
}
DEFAULT_COLOR = (0.55, 0.55, 0.55)


def building_to_primitives(p: config_mod.BuildingParams) -> list[gltf_mod.Primitive]:
    """建筑 → glTF primitives（台基 / 柱网 / [斗拱] / 屋顶）。"""
    parts, _pl = build_building_parts(p)
    return [gltf_mod.Primitive(comp, m, PLACEHOLDER_COLORS[comp]) for comp, m in parts]


def scene_to_primitives(scene: config_mod.Scene, scene_path: str) -> list[gltf_mod.Primitive]:
    """景群 → glTF primitives（逐栋逐构件，颜色按构件类型）。"""
    prims: list[gltf_mod.Primitive] = []
    for label, m in scene_mod.build_scene(scene, scene_path):
        comp = label.rsplit("/", 1)[-1]
        prims.append(gltf_mod.Primitive(label, m, PLACEHOLDER_COLORS.get(comp, DEFAULT_COLOR)))
    return prims


def garden_to_primitives(garden: config_mod.Garden, garden_path: str) -> list[gltf_mod.Primitive]:
    """总园 → glTF primitives（景内构件 + 示意湖面）。"""
    prims: list[gltf_mod.Primitive] = []
    for label, m in scene_mod.build_garden(garden, garden_path):
        comp = label.rsplit("/", 1)[-1]
        prims.append(gltf_mod.Primitive(label, m, PLACEHOLDER_COLORS.get(comp, DEFAULT_COLOR)))
    return prims


def main() -> int:
    ap = argparse.ArgumentParser(description="圆明园 · glb 导出（纯 Python，无需 Blender）")
    ap.add_argument("--config", default=None, help="建筑参数 YAML 路径（单栋）")
    ap.add_argument("--scene", default=None, help="场景 YAML 路径（景群，多栋）")
    ap.add_argument("--garden", default=None, help="总园 YAML 路径（多景 + 示意湖面）")
    ap.add_argument("--out", required=True, help="输出 .glb 路径")
    args = ap.parse_args()
    if sum([bool(args.config), bool(args.scene), bool(args.garden)]) != 1:
        ap.error("--config / --scene / --garden 须且仅须提供一个")

    if args.config:
        p = config_mod.load_building(args.config)
        prims = building_to_primitives(p)
        title = f"{p.name}（{p.id}）"
    elif args.scene:
        sc = config_mod.load_scene(args.scene)
        prims = scene_to_primitives(sc, args.scene)
        title = f"{sc.name}（{sc.id}，{len(sc.buildings)} 栋）"
    else:
        g = config_mod.load_garden(args.garden)
        prims = garden_to_primitives(g, args.garden)
        title = f"{g.name}（{g.id}，{len(g.scenes)} 景 / {len(g.lakes)} 湖）"

    blob = gltf_mod.build_glb(prims)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(blob)
    n_verts = sum(len(pr.mesh.vertices) for pr in prims)
    n_faces = sum(len(pr.mesh.faces) for pr in prims)
    print(f"[export] {title} → {out}")
    print(f"[export] {n_verts} 顶点 / {n_faces} 面 / {len(prims)} 构件，glb {len(blob):,} 字节")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
