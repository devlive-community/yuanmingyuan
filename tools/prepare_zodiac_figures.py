"""prepare_zodiac_figures.py — 把单图生成 3D 的整尊生肖铜像整理成生成器可用的网格（仅 Blender 内运行）。

用于参考图效果版（ADR-0003）：铜像由用户提供的参考效果图逐尊截图，经 TripoSR（本机，MIT 许可）生成，
原始结果在 ``assets/zodiac_figures/raw/*.obj``（TripoSR 坐标：z 向上）。

处理：合并重合顶点 → 减面到约 TARGET_FACES → 平滑重建噪点 → 以兽首吻部定朝向 →
底面中心对齐原点、高度归一为 1 → 写出 ``assets/zodiac_figures/<名>.obj``，局部系 +a 前 / +b 左 / +h 上。

用法（缺省处理 assets/zodiac_figures；史料版坐像：-- assets/zodiac_seated/raw assets/zodiac_seated）：

    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P tools/prepare_zodiac_figures.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "assets" / "zodiac_figures" / "raw"
OUT = ROOT / "assets" / "zodiac_figures"
TARGET_FACES = 24000             # 每尊约两万四千三角面：衣褶可辨，十二尊合计仍可实时
SMOOTH_ITERATIONS = 2            # 去掉单图重建的颗粒噪点，保留衣褶大形
HEAD_BAND = (0.72, 0.95)         # 兽首所在的高度带（占通高比例）：吻端取此带内离躯干轴最远的点


def prepare(src: Path, dst: Path, yaw_override: float | None = None) -> tuple[int, float]:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.obj_import(filepath=str(src), forward_axis="Y", up_axis="Z")
    obj = bpy.context.selected_objects[0]
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=1e-6)
    bpy.ops.object.mode_set(mode="OBJECT")
    n = len(obj.data.polygons)
    if n > TARGET_FACES:
        mod = obj.modifiers.new("decimate", "DECIMATE")
        mod.ratio = TARGET_FACES / n
        bpy.ops.object.modifier_apply(modifier=mod.name)
    mod = obj.modifiers.new("smooth", "LAPLACIANSMOOTH")
    mod.iterations = SMOOTH_ITERATIONS
    mod.lambda_factor = 0.4
    mod.use_volume_preserve = True
    bpy.ops.object.modifier_apply(modifier=mod.name)

    pts = [tuple(v.co) for v in obj.data.vertices]
    zmin = min(p[2] for p in pts)
    h = max(p[2] for p in pts) - zmin
    base = [p for p in pts if p[2] < zmin + 0.08 * h]                 # 底座：定躯干竖轴
    cx = sum(p[0] for p in base) / len(base)
    cy = sum(p[1] for p in base) / len(base)
    band = [p for p in pts if zmin + HEAD_BAND[0] * h <= p[2] <= zmin + HEAD_BAND[1] * h]
    hx = sum(p[0] for p in band) / len(band)
    hy = sum(p[1] for p in band) / len(band)
    snout = max(band, key=lambda p: (p[0] - hx) ** 2 + (p[1] - hy) ** 2)
    yaw = math.atan2(snout[1] - hy, snout[0] - hx)                      # 吻部方向 = 铜像正面
    if yaw_override is not None:                                         # 手持长杖等会干扰吻部判断时手动指定
        yaw = math.radians(yaw_override)
    c, s = math.cos(-yaw), math.sin(-yaw)
    k = 1.0 / h
    with dst.open("w", encoding="utf-8") as f:
        f.write(f"# {dst.stem}: from {src.name} (TripoSR), prepared by tools/prepare_zodiac_figures.py; local a/b/h, height 1\n")
        for x, y, z in pts:
            dx, dy = x - cx, y - cy
            f.write(f"v {(dx * c - dy * s) * k:.5f} {(dx * s + dy * c) * k:.5f} {(z - zmin) * k:.5f}\n")
        for p in obj.data.polygons:
            f.write("f " + " ".join(str(i + 1) for i in p.vertices) + "\n")
    return len(obj.data.polygons), math.degrees(yaw)


def main() -> int:
    global RAW, OUT
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(argv) == 2:                                               # 可选：-- <输入 raw 目录> <输出目录>
        RAW, OUT = ROOT / argv[0], ROOT / argv[1]
    srcs = sorted(RAW.glob("*.obj")) if RAW.exists() else []
    if not srcs:
        print(f"[figures] {RAW} 中没有 .obj")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    import json

    orient = json.loads((RAW / "orientation.json").read_text()) if (RAW / "orientation.json").exists() else {}
    for src in srcs:
        o = orient.get(src.stem, {})
        faces, yaw = prepare(src, OUT / src.name, o.get("yaw"))
        print(f"[figures] {src.name}: {faces} 面，正面方位 {yaw:.0f}°")
    return 0


if __name__ == "__main__":
    sys.exit(main())
