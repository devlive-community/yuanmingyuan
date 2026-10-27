"""prepare_zodiac_heads.py — 把外部生成 / 扫描的生肖兽首模型整理成生成器可用的网格（仅 Blender 内运行）。

输入：``assets/zodiac_heads/raw/<生肖英文名>.<glb|gltf|obj|fbx|stl>``（如 ox.glb、monkey.glb），
     可选 ``assets/zodiac_heads/raw/orientation.json``：{"ox": {"yaw": 90}} —— 朝向不对时按生肖绕竖轴补转（度）；
     {"ox": {"source": "triposr"}} —— TripoSR 本机生成的 OBJ（z 向上、正面朝 +x，照片正面拍摄时成立）。
输出：``assets/zodiac_heads/<生肖英文名>.obj``（只含顶点与面），坐标为生成器的兽首局部系：
     +a 朝前（吻部方向）、+b 向左、+h 向上；底面中心在原点；高度归一为 HEAD_HEIGHT（与 sculpt.py 雕塑兽首同高）。

处理：合并全部网格 → 去重合并顶点 → 减面到约 TARGET_FACES 个三角形 → 按包围盒对齐底面中心、缩放到统一高度。
默认认为模型在 Blender 里「面朝 −Y」（即 glTF 的面朝 +Z，图生 3D 工具的通常朝向）；不是的话在 orientation.json 里补转。

用法：

    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P tools/prepare_zodiac_heads.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "assets" / "zodiac_heads" / "raw"
OUT = ROOT / "assets" / "zodiac_heads"
KINDS = ("rat", "ox", "tiger", "rabbit", "dragon", "snake", "horse", "goat", "monkey", "rooster", "dog", "pig")
TARGET_FACES = 12000             # 每首约一万二千三角面：近看有雕刻细节，十二首合计仍可实时
HEAD_HEIGHT = 34.0               # 与 sculpt.animal_head 雕塑兽首连颈同高（局部单位，scale = 1 时为 cm）

IMPORTERS = {
    ".glb": lambda p: bpy.ops.import_scene.gltf(filepath=str(p)),
    ".gltf": lambda p: bpy.ops.import_scene.gltf(filepath=str(p)),
    ".obj": lambda p: bpy.ops.wm.obj_import(filepath=str(p)),
    ".fbx": lambda p: bpy.ops.import_scene.fbx(filepath=str(p)),
    ".stl": lambda p: bpy.ops.wm.stl_import(filepath=str(p)),
}


def _cut_stand(obj, frac: float = 0.35, slices: int = 60) -> None:
    """截掉照片里展台的支杆与底板：下部 40% 高度内最细的截面（支杆）若窄于最大宽 ``frac``，其下全部删去。"""
    import bmesh

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    zs = [v.co.z for v in bm.verts]
    z0, z1 = min(zs), max(zs)
    dz = (z1 - z0) / slices
    widths = []
    for k in range(slices):
        band = [v.co for v in bm.verts if z0 + k * dz <= v.co.z < z0 + (k + 1) * dz]
        widths.append(max((max(c.x for c in band) - min(c.x for c in band)) if band else 0.0,
                          (max(c.y for c in band) - min(c.y for c in band)) if band else 0.0))
    wmax = max(widths)
    lower = [(wv, k) for k, wv in enumerate(widths[: int(slices * 0.4)]) if wv > 0]
    wmin, kmin = min(lower) if lower else (wmax, 0)
    cut = z0 + (kmin + 1) * dz if wmin < frac * wmax else z0   # 支杆处（下部最细截面）以下全部删去
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < cut], context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()


def prepare(kind: str, src: Path, yaw_deg: float, triposr: bool = False) -> int:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if triposr:                                                      # 保持原坐标：z 向上
        bpy.ops.wm.obj_import(filepath=str(src), forward_axis="Y", up_axis="Z")
    else:
        IMPORTERS[src.suffix.lower()](src)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"{src} 中没有网格")
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)   # 父级与导入变换落到顶点
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=1e-5)
    bpy.ops.mesh.quads_convert_to_tris()
    bpy.ops.object.mode_set(mode="OBJECT")
    n = len(obj.data.polygons)
    if n > TARGET_FACES:
        mod = obj.modifiers.new("decimate", "DECIMATE")
        mod.ratio = TARGET_FACES / n
        bpy.ops.object.modifier_apply(modifier=mod.name)

    if triposr:                                                      # 单图重建的颗粒噪点：轻度平滑
        mod = obj.modifiers.new("smooth", "LAPLACIANSMOOTH")
        mod.iterations = 2
        mod.lambda_factor = 0.4
        mod.use_volume_preserve = True
        bpy.ops.object.modifier_apply(modifier=mod.name)
        _cut_stand(obj)
    me = obj.data
    yaw = math.radians(yaw_deg)
    c, s = math.cos(yaw), math.sin(yaw)
    pts = []
    for v in me.vertices:
        x, y, z = v.co
        x, y = x * c - y * s, x * s + y * c                          # 补转
        pts.append((x, y, z) if triposr else (-y, x, z))             # 面朝 +x（TripoSR）/ −Y → 局部 (a 前, b 左, h 上)
    amin = min(p[0] for p in pts); amax = max(p[0] for p in pts)
    bmin = min(p[1] for p in pts); bmax = max(p[1] for p in pts)
    hmin = min(p[2] for p in pts); hmax = max(p[2] for p in pts)
    k = HEAD_HEIGHT / max(1e-9, hmax - hmin)
    ca, cb = (amin + amax) / 2.0, (bmin + bmax) / 2.0
    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / f"{kind}.obj"
    with dst.open("w", encoding="utf-8") as f:
        f.write(f"# {kind}: from {src.name}, prepared by tools/prepare_zodiac_heads.py (local a/b/h, cm @ scale 1)\n")
        for a, b, h in pts:
            f.write(f"v {(a - ca) * k:.3f} {(b - cb) * k:.3f} {(h - hmin) * k:.3f}\n")
        for p in me.polygons:
            f.write("f " + " ".join(str(i + 1) for i in p.vertices) + "\n")
    return len(me.polygons)


def main() -> int:
    if not RAW.exists():
        print(f"[heads] 未找到 {RAW}：把兽首模型放进该目录（如 ox.glb）后再运行")
        return 1
    orient = json.loads((RAW / "orientation.json").read_text()) if (RAW / "orientation.json").exists() else {}
    done = 0
    for kind in KINDS:
        srcs = [p for p in RAW.glob(f"{kind}.*") if p.suffix.lower() in IMPORTERS]
        if not srcs:
            continue
        o = orient.get(kind, {})
        faces = prepare(kind, srcs[0], float(o.get("yaw", 0.0)), o.get("source") == "triposr")
        print(f"[heads] {kind}: {srcs[0].name} → assets/zodiac_heads/{kind}.obj（{faces} 面）")
        done += 1
    print(f"[heads] 完成 {done} / {len(KINDS)} 首；其余继续用雕塑兽首")
    return 0


if __name__ == "__main__":
    sys.exit(main())
