"""cycles_render.py — 用 Blender Cycles 渲染景区静帧（照片级效果图管线）。

几何来自生成器导出的 glb（与网页查看器同一份），材质按网格标签末段（材质类 id）
在 Blender 中以 PBR 节点重建；设色依据同 web/app/src/viewer/materials.ts（见 docs/speculative.md S-013）。

用法（``--`` 之后为脚本参数）：

    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \\
        -P blender/render/cycles_render.py -- \\
        --glb build/haiyantang.glb --out build/renders/haiyantang_west.png --view west

坐标：glb 导入后与生成器场景坐标一致（米，+X 东、+Y 北、Z 上）。
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

UP = Vector((0.0, 0.0, 1.0))
SUN_DIR = Vector((-0.55, -0.56, 0.62)).normalized()   # 西南来光（午后），照亮西向正立面；与网页一致

# 视角：(相机位置, 注视点, 焦距 mm)；坐标为海晏堂局部系（原点 = 蓄水楼中心）
VIEWS = {
    "west": ((-128.0, -14.0, 15.0), (-46.0, 0.0, 8.0), 30.0),       # 铜版画「海晏堂西面」视点
    "south": ((-6.0, -100.0, 16.0), (-8.0, 0.0, 7.0), 30.0),
    "east": ((92.0, 18.0, 14.0), (20.0, 0.0, 8.0), 32.0),
    "aerial": ((-125.0, -115.0, 75.0), (-18.0, 0.0, 2.0), 32.0),
}


# ---------------------------------------------------------------------------
# 材质（节点工具）
# ---------------------------------------------------------------------------

def _rgb(hex_color: str) -> tuple[float, float, float, float]:
    """sRGB 十六进制 → 线性 RGBA（Principled 输入为线性）。"""
    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    h = hex_color.lstrip("#")
    return (*(lin(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4)), 1.0)


def _socket(node, *names):
    for n in names:
        if n in node.inputs:
            return node.inputs[n]
    raise KeyError(names)


class MatBuilder:
    """一个 Principled 材质的节点搭建器：UV（米）→ 程序纹理 → 颜色 / 粗糙度 / 凹凸。"""

    def __init__(self, name: str):
        self.mat = bpy.data.materials.new(name)
        self.mat.use_nodes = True
        self.nt = self.mat.node_tree
        self.nodes = self.nt.nodes
        self.bsdf = self.nodes["Principled BSDF"]
        self.uv = self.nodes.new("ShaderNodeTexCoord").outputs["UV"]

    def link(self, a, b):
        self.nt.links.new(a, b)

    def set(self, *names, value):
        _socket(self.bsdf, *names).default_value = value

    def noise(self, scale: float, detail: float = 8.0, distortion: float = 0.0):
        n = self.nodes.new("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        n.inputs["Distortion"].default_value = distortion
        self.link(self.uv, n.inputs["Vector"])
        return n

    def ramp(self, src, c0: str, c1: str, p0: float = 0.3, p1: float = 0.7):
        r = self.nodes.new("ShaderNodeValToRGB")
        r.color_ramp.elements[0].position, r.color_ramp.elements[0].color = p0, _rgb(c0)
        r.color_ramp.elements[1].position, r.color_ramp.elements[1].color = p1, _rgb(c1)
        self.link(src, r.inputs["Fac"])
        return r.outputs["Color"]

    def bump(self, height, strength: float, distance: float = 0.02):
        b = self.nodes.new("ShaderNodeBump")
        b.inputs["Strength"].default_value = strength
        b.inputs["Distance"].default_value = distance
        self.link(height, b.inputs["Height"])
        self.link(b.outputs["Normal"], _socket(self.bsdf, "Normal"))


def build_materials() -> dict[str, bpy.types.Material]:
    """材质类表；键与网格标签末段一致。"""
    mats: dict[str, bpy.types.Material] = {}

    def plaster(name, base, dark, rough=0.9, scale=6.0, bump=0.12):
        m = MatBuilder(name)
        n = m.noise(scale, 12.0)
        m.link(m.ramp(n.outputs["Fac"], dark, base), _socket(m.bsdf, "Base Color"))
        m.set("Roughness", value=rough)
        m.bump(n.outputs["Fac"], bump, 0.01)
        return m.mat

    mats["walls"] = plaster("walls", "#c9968a", "#b48176")             # 粉红色灰（维基，medium）

    m = MatBuilder("marble")                                           # 汉白玉：脉纹 + 微抛光
    veins = m.nodes.new("ShaderNodeTexWave")
    veins.inputs["Scale"].default_value = 0.05
    veins.inputs["Distortion"].default_value = 4.0
    veins.inputs["Detail"].default_value = 6.0
    m.link(m.uv, veins.inputs["Vector"])
    m.link(m.ramp(veins.outputs["Fac"], "#cfcac0", "#e4e0d7", 0.0, 0.12), _socket(m.bsdf, "Base Color"))
    m.set("Roughness", value=0.32)
    m.bump(m.noise(30.0).outputs["Fac"], 0.05, 0.005)
    mats["marble"] = m.mat

    m = MatBuilder("limestone")                                        # 参考图效果版：米白石材（非史料）
    veins = m.nodes.new("ShaderNodeTexWave")
    veins.inputs["Scale"].default_value = 0.04
    veins.inputs["Distortion"].default_value = 3.0
    veins.inputs["Detail"].default_value = 4.0
    m.link(m.uv, veins.inputs["Vector"])
    m.link(m.ramp(veins.outputs["Fac"], "#cdbf9f", "#e8dcc2", 0.0, 0.2), _socket(m.bsdf, "Base Color"))
    m.set("Roughness", value=0.55)
    m.bump(m.noise(20.0).outputs["Fac"], 0.08, 0.005)
    mats["limestone"] = m.mat
    mats["recess"] = plaster("recess", "#3b352e", "#2c2722", rough=0.95)    # 券洞内暗面

    def glazed(name, base, dark, coat=0.6, period=0.3):
        m = MatBuilder(name)                                           # 琉璃筒瓦：顺坡瓦垄 + 釉面清漆
        w = m.nodes.new("ShaderNodeTexWave")
        w.wave_type, w.bands_direction = "BANDS", "X"
        w.wave_profile = "SIN"
        w.inputs["Scale"].default_value = 1.0 / period / 3.0          # UV 以米计：每 period 米一垄
        m.link(m.uv, w.inputs["Vector"])
        m.link(m.ramp(w.outputs["Fac"], dark, base, 0.1, 0.9), _socket(m.bsdf, "Base Color"))
        m.set("Roughness", value=0.18)
        try:
            m.set("Coat Weight", value=coat)
        except KeyError:
            pass
        m.bump(w.outputs["Fac"], 0.8, 0.04)
        return m.mat

    mats["glazed_roof"] = glazed("glazed_roof", "#2c8a6d", "#15503f")      # 孔雀绿琉璃（medium）
    mats["glazed_ridge"] = glazed("glazed_ridge", "#dca431", "#9a6a14", period=0.5)   # 黄琉璃脊（medium）
    mats["roof"] = glazed("roof", "#5f636a", "#33363b", coat=0.0)          # 灰筒瓦（谕旨，high）

    m = MatBuilder("gold_roof")                                         # 鱼鳞金瓦
    vor = m.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 6.0
    m.link(m.uv, vor.inputs["Vector"])
    m.link(m.ramp(vor.outputs["Distance"], "#e2b75a", "#8d6a22"), _socket(m.bsdf, "Base Color"))
    m.set("Metallic", value=0.9)
    m.set("Roughness", value=0.3)
    m.bump(vor.outputs["Distance"], 0.5, 0.02)
    mats["gold_roof"] = m.mat

    def slabs(name, base, mortar, size=0.8):
        m = MatBuilder(name)                                            # 石板：砖纹作缝 + 噪声起伏
        b = m.nodes.new("ShaderNodeTexBrick")
        b.inputs["Scale"].default_value = 1.0 / size
        b.inputs["Mortar Size"].default_value = 0.012
        b.inputs["Color1"].default_value = _rgb(base)
        b.inputs["Color2"].default_value = _rgb(base)
        b.inputs["Mortar"].default_value = _rgb(mortar)
        b.offset = 0.5
        m.link(m.uv, b.inputs["Vector"])
        mix = m.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        sock = {s.identifier: s for s in mix.inputs}
        out = {s.identifier: s for s in mix.outputs}
        sock["Factor_Float"].default_value = 0.35
        m.link(b.outputs["Color"], sock["A_Color"])                      # 同名插槽按标识符取颜色型
        m.link(m.ramp(m.noise(4.0).outputs["Fac"], "#9a9a9a", "#ffffff"), sock["B_Color"])
        m.link(out["Result_Color"], _socket(m.bsdf, "Base Color"))
        m.set("Roughness", value=0.8)
        m.bump(b.outputs["Fac"], 0.4, 0.01)
        return m.mat

    mats["paving"] = slabs("paving", "#aaa293", "#5d584f")
    mats["platform"] = slabs("platform", "#bdb6a7", "#6a655c")

    m = MatBuilder("windows")                                           # 法式铜窗：深色玻璃 + 铜窗棂
    grid = m.nodes.new("ShaderNodeTexBrick")
    grid.inputs["Scale"].default_value = 2.5
    grid.inputs["Mortar Size"].default_value = 0.04
    grid.offset = 0.0
    grid.inputs["Color1"].default_value = (0, 0, 0, 1)
    grid.inputs["Color2"].default_value = (0, 0, 0, 1)
    grid.inputs["Mortar"].default_value = (1, 1, 1, 1)
    m.link(m.uv, grid.inputs["Vector"])
    glass = m.nodes.new("ShaderNodeBsdfPrincipled")
    glass.inputs["Base Color"].default_value = _rgb("#1b262b")
    glass.inputs["Roughness"].default_value = 0.04
    m.set("Base Color", value=_rgb("#7a5a32"))
    m.set("Metallic", value=1.0)
    m.set("Roughness", value=0.35)
    mix = m.nodes.new("ShaderNodeMixShader")
    m.link(grid.outputs["Fac"], mix.inputs["Fac"])
    m.link(glass.outputs["BSDF"], mix.inputs[1])
    m.link(m.bsdf.outputs["BSDF"], mix.inputs[2])
    m.link(mix.outputs["Shader"], m.nodes["Material Output"].inputs["Surface"])
    mats["windows"] = m.mat

    def water(name, color):
        m = MatBuilder(name)
        m.set("Base Color", value=_rgb(color))
        m.set("Roughness", value=0.02)
        m.set("IOR", value=1.33)
        m.set("Transmission Weight", "Transmission", value=1.0)
        m.bump(m.noise(3.0, 4.0).outputs["Fac"], 0.08, 0.02)
        return m.mat

    mats["water"] = water("water", "#7fb3bd")
    m = MatBuilder("cascade")                                          # 导水台：湿石面上的薄水（不透射）
    m.set("Base Color", value=_rgb("#9fb9bf"))
    m.set("Roughness", value=0.05)
    m.bump(m.noise(6.0, 4.0).outputs["Fac"], 0.15, 0.01)
    mats["cascade"] = m.mat
    mats["jet"] = water("jet", "#eef7ff")

    def metal(name, color, rough):
        m = MatBuilder(name)
        n = m.noise(12.0)
        m.link(m.ramp(n.outputs["Fac"], color, "#3f5a4a" if name == "bronze" else color, 0.55, 0.95),
               _socket(m.bsdf, "Base Color"))                          # 铜绿锈斑
        m.set("Metallic", value=1.0)
        m.set("Roughness", value=rough)
        return m.mat

    mats["bronze"] = metal("bronze", "#7a5530", 0.35)
    mats["tin"] = metal("tin", "#b5b9bd", 0.25)
    mats["columns"] = plaster("columns", "#7a1a10", "#5e130b", rough=0.4, scale=3.0, bump=0.03)  # 朱红油饰
    mats["brackets"] = plaster("brackets", "#2f635a", "#1f4740", rough=0.6)
    mats["beams"] = plaster("beams", "#2b5862", "#1d3f47", rough=0.6)                      # 檐枋青绿（占位，S-042）
    mats["red_wall"] = plaster("red_wall", "#a4412f", "#86321f")                             # 红灰墙（占位，S-042）
    mats["wall_base"] = slabs("wall_base", "#8f8e88", "#b9b5aa", size=0.3)                   # 青砖下碱
    mats["joinery"] = plaster("joinery", "#7a1a10", "#5e130b", rough=0.45, scale=3.0, bump=0.03)  # 朱红装修
    mats["paper"] = plaster("paper", "#e4dac2", "#cfc4aa", rough=0.95, bump=0.02)            # 窗户纸
    mats["foliage"] = plaster("foliage", "#3e5f2a", "#22381a", rough=0.85, scale=18.0, bump=0.9)
    mats["bark"] = plaster("bark", "#5b4632", "#3a2c1f", rough=0.95, scale=10.0, bump=0.6)
    mats["ground"] = plaster("ground", "#6f8346", "#4c5f30", rough=0.95, scale=1.5, bump=0.3)
    mats["island"] = plaster("island", "#857c62", "#6a624c", rough=0.95, scale=2.0)
    mats["_default"] = plaster("_default", "#a8a39a", "#8f8a81")
    return mats


# ---------------------------------------------------------------------------
# 几何处理
# ---------------------------------------------------------------------------

def planar_uvs(obj) -> None:
    """逐面平面投影 UV（米）：u 沿水平切向、v 沿面内上坡向；瓦垄顺坡、石缝与窗棂横平竖直。"""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    uv = bm.loops.layers.uv.verify()
    mw = obj.matrix_world
    for f in bm.faces:
        n = (mw.to_3x3() @ f.normal).normalized()
        t = UP.cross(n)
        t = Vector((1.0, 0.0, 0.0)) if t.length < 1e-4 else t.normalized()
        b = n.cross(t).normalized()
        for loop in f.loops:
            p = mw @ loop.vert.co
            loop[uv].uv = (p.dot(t), p.dot(b))
    bm.to_mesh(obj.data)
    bm.free()


def jet_endpoints(obj) -> tuple[Vector, Vector]:
    """喷水标记（beam：前 4 顶点在喷口端、后 4 顶点在落点端）。"""
    vs = [obj.matrix_world @ v.co for v in obj.data.vertices]
    return sum(vs[:4], Vector()) / 4.0, sum(vs[4:8], Vector()) / 4.0


def water_tube(points: list[Vector], radius: float, mat) -> None:
    curve = bpy.data.curves.new("jet", "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = radius
    curve.bevel_resolution = 2
    spl = curve.splines.new("POLY")
    spl.points.add(len(points) - 1)
    for p, pt in zip(spl.points, points):
        p.co = (*pt, 1.0)
    obj = bpy.data.objects.new("jet", curve)
    obj.data.materials.append(mat)
    bpy.context.scene.collection.objects.link(obj)


def parabola(a: Vector, b: Vector, arc: float, n: int = 24) -> list[Vector]:
    return [a.lerp(b, k / n) + UP * (4.0 * arc * (k / n) * (1 - k / n)) for k in range(n + 1)]


def build_jets(jets: list[tuple[Vector, Vector]], mat) -> None:
    """抛物线水柱；竖直标记生成伞状喷泉（8 道向外落下的水弧 + 中心水柱）。"""
    for a, b in jets:
        horiz = Vector((b.x - a.x, b.y - a.y, 0.0))
        if horiz.length > 0.05:
            water_tube(parabola(a, b, max(0.25, horiz.length * 0.28)), 0.018, mat)
            continue
        h = b.z - a.z
        water_tube([a, b], 0.03, mat)
        for k in range(8):
            ang = 2 * math.pi * k / 8
            land = a + Vector((math.cos(ang), math.sin(ang), 0.0)) * (h * 0.35)
            water_tube(parabola(b, land, h * 0.15), 0.012, mat)


# ---------------------------------------------------------------------------
# 场景
# ---------------------------------------------------------------------------

def setup_world() -> None:
    world = bpy.data.worlds.new("sky")
    world.use_nodes = True
    nt = world.node_tree
    sky = nt.nodes.new("ShaderNodeTexSky")
    types = [e.identifier for e in sky.bl_rna.properties["sky_type"].enum_items]
    sky.sky_type = next(t for t in ("MULTIPLE_SCATTERING", "NISHITA", "SINGLE_SCATTERING", "HOSEK_WILKIE") if t in types)
    sky.sun_disc = False                                       # 直射光由太阳灯提供
    sky.sun_elevation = math.asin(SUN_DIR.z)
    sky.sun_rotation = math.atan2(SUN_DIR.x, SUN_DIR.y) + math.pi
    bg = nt.nodes["Background"]
    bg.inputs["Strength"].default_value = 0.22
    nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
    bpy.context.scene.world = world

    sun = bpy.data.lights.new("sun", "SUN")
    sun.energy = 6.5
    sun.angle = math.radians(0.6)
    sun.color = (1.0, 0.95, 0.88)
    obj = bpy.data.objects.new("sun", sun)
    obj.rotation_euler = SUN_DIR.to_track_quat("Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(obj)


def add_ground(mat, size: float = 6000.0) -> None:
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0.0, 0.0, -0.06))
    g = bpy.context.active_object
    g.name = "ground"
    g.data.materials.append(mat)
    planar_uvs(g)


def add_camera(view: str) -> None:
    loc, target, lens = VIEWS[view]
    cam = bpy.data.cameras.new("cam")
    cam.lens = lens
    cam.clip_end = 3000.0
    obj = bpy.data.objects.new("cam", cam)
    obj.location = loc
    obj.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.scene.camera = obj


def setup_render(out: Path, samples: int, width: int, height: int) -> None:
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    try:
        prefs.compute_device_type = "METAL"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type == "METAL"
        sc.cycles.device = "GPU"
    except Exception:                                          # 无 GPU 时退回 CPU
        sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = width, height
    for vt in ("AgX", "Filmic", "Standard"):
        try:
            sc.view_settings.view_transform = vt
            break
        except TypeError:
            continue
    sc.view_settings.exposure = -0.2
    looks = [e.identifier for e in sc.view_settings.bl_rna.properties["look"].enum_items]
    for look in ("AgX - Medium High Contrast", "Medium High Contrast"):
        if look in looks:
            sc.view_settings.look = look
            break
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = str(out)


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(description="圆明园 · Cycles 效果图")
    ap.add_argument("--glb", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--view", choices=sorted(VIEWS), default="west")
    ap.add_argument("--samples", type=int, default=96)
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    args = ap.parse_args(argv)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(Path(args.glb).resolve()))
    mats = build_materials()

    jets: list[tuple[Vector, Vector]] = []
    for obj in list(bpy.context.scene.objects):
        if obj.type != "MESH":
            continue
        key = str(obj.get("label", obj.name)).split("/")[-1]
        if key == "jet":
            jets.append(jet_endpoints(obj))
            bpy.data.objects.remove(obj, do_unlink=True)
            continue
        if key == "viewpoint":                                           # 人视标记：不渲染
            bpy.data.objects.remove(obj, do_unlink=True)
            continue
        planar_uvs(obj)
        obj.data.materials.clear()
        obj.data.materials.append(mats.get(key, mats["_default"]))
        for poly in obj.data.polygons:
            poly.use_smooth = False
    build_jets(jets, mats["jet"])
    add_ground(mats["ground"])
    setup_world()
    add_camera(args.view)
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    setup_render(out, args.samples, args.width, args.height)
    bpy.ops.render.render(write_still=True)
    print(f"[cycles] {out}（{len(jets)} 道水柱）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
