"""bake_scene.py — 为网页实时漫游烘焙「倒角 + 天光全局光照贴图」（游戏式光照）。

输入生成器导出的 glb，输出倒角后的 glb：
- 每个烘焙对象一张光照贴图（按表面积定分辨率，约 24 px/m），内嵌为该对象材质的颜色贴图（WebP），
  UV 为其唯一一套（TEXCOORD_0）；浏览器把它当作 lightMap 使用；
- 光照内容：天空光（含天空遮蔽与墙、地、屋面间的反弹），× 0.5 编码，浏览器端 lightMapIntensity = 2；
- 节点 extras 保留 label / jet；未烘焙对象（水、玻璃、喷水标记）不带贴图。

太阳直射不烘焙：浏览器中由实时太阳与阴影提供，避免重复计光。

用法（``--`` 之后为脚本参数）：

    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \\
        -P blender/render/bake_scene.py -- \\
        --glb build/haiyantang.glb --out-glb build/baked/haiyantang.glb --samples 128
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cycles_render as cr  # noqa: E402  —— 复用材质、平面 UV、天空与地面

NO_BAKE = {"water", "cascade", "windows", "jet", "viewpoint", "leaves"}   # 透明 / 动态 / 标记：不烘焙、不倒角
NO_BEVEL = NO_BAKE | {"foliage", "bark"}
BEVEL_WIDTH_M = 0.03
BEVEL_ANGLE_DEG = 70.0                                   # 只倒直角硬边；栏杆柱等多棱柱不倒
TEXELS_PER_M = 24.0                                      # 光照贴图密度（约 4 cm / 像素）
LM_MIN, LM_MAX = 64, 2048
LIGHTMAP_SCALE = 0.5                                     # 存储编码：L × 0.5（浏览器端 ×2 还原）
SMOOTH_ANGLE_DEG = 40.0                                  # 按角平滑：与浏览器端折角阈值一致（旋转体、团块不显棱面）


def smooth_by_angle(obj) -> None:
    """夹角小于阈值的相邻面平滑着色，大于阈值保持硬边（烘焙法线与浏览器端一致）。"""
    import math

    obj.data.shade_smooth()
    obj.data.set_sharp_from_angle(angle=math.radians(SMOOTH_ANGLE_DEG))


def key_of(obj) -> str:
    return str(obj.get("label", obj.name)).split("/")[-1]


def bevel(obj) -> None:
    """倒角修改器求值后写回网格（不依赖操作符上下文）。"""
    mod = obj.modifiers.new("bevel", "BEVEL")
    mod.width = BEVEL_WIDTH_M
    mod.segments = 1                                     # 单段倒角（斜切）：保留边线高光，顶点最省
    mod.limit_method = "ANGLE"
    mod.angle_limit = BEVEL_ANGLE_DEG * 3.14159265 / 180.0
    mod.use_clamp_overlap = True
    deps = bpy.context.evaluated_depsgraph_get()
    new = bpy.data.meshes.new_from_object(obj.evaluated_get(deps))
    obj.modifiers.remove(mod)
    old = obj.data
    obj.data = new
    bpy.data.meshes.remove(old)


def lightmap_size(obj) -> int:
    """按世界空间表面积定光照贴图边长（2 的幂）。"""
    area = sum(p.area for p in obj.data.polygons) * max(obj.scale) ** 2
    side = (area ** 0.5) * TEXELS_PER_M
    size = LM_MIN
    while size < side and size < LM_MAX:
        size *= 2
    return size


def lightmap_uvs(objs: list) -> None:
    """每个对象单独一张光照图：新增 lightmap UV 层并以「光照贴图排布」逐对象展开。"""
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
        lm = o.data.uv_layers.get("lightmap") or o.data.uv_layers.new(name="lightmap")
        o.data.uv_layers.active = lm
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.lightmap_pack(PREF_CONTEXT="ALL_FACES", PREF_PACK_IN_ONE=False, PREF_NEW_UVLAYER=False,
                             PREF_BOX_DIV=12, PREF_MARGIN_DIV=0.3)
    bpy.ops.object.mode_set(mode="OBJECT")


def attach_bake_images(objs: list) -> dict:
    """每个对象复制一份材质并挂上自己的光照图（Cycles 烘焙写入材质的活动图像节点）。"""
    images = {}
    for o in objs:
        mat = o.material_slots[0].material.copy()
        o.material_slots[0].material = mat
        size = lightmap_size(o)
        img = bpy.data.images.new(f"lm_{o.name}", size, size, float_buffer=True)
        node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = img
        mat.node_tree.nodes.active = node
        images[o.name] = img
    return images


def lightmap_material(obj, image):
    """导出用材质：颜色贴图 = 光照图（×LIGHTMAP_SCALE 编码进 8 位 sRGB），UV = lightmap。"""
    import numpy as np

    px = np.empty(len(image.pixels), dtype=np.float32)
    image.pixels.foreach_get(px)
    px = px.reshape(-1, 4)
    px[:, :3] = np.clip(px[:, :3] * LIGHTMAP_SCALE, 0.0, 1.0)
    px[:, 3] = 1.0
    out = bpy.data.images.new(f"lightmap_{obj.name}", image.size[0], image.size[1], float_buffer=False)
    out.pixels.foreach_set(px.ravel())
    out.file_format = "WEBP"
    out.pack()
    mat = bpy.data.materials.new(f"lm_{obj.name}")
    mat.use_nodes = True
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = out
    mat.node_tree.links.new(tex.outputs["Color"], mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    return mat


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(description="圆明园 · 倒角 + 光照贴图烘焙")
    ap.add_argument("--glb", required=True)
    ap.add_argument("--out-glb", required=True)
    ap.add_argument("--samples", type=int, default=128)
    args = ap.parse_args(argv)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(Path(args.glb).resolve()))
    mats = cr.build_materials()
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    bake_objs = []
    for o in meshes:
        key = key_of(o)
        if key in ("jet", "viewpoint"):
            continue
        if key not in NO_BEVEL:
            bevel(o)
        smooth_by_angle(o)
        cr.planar_uvs(o)                                 # UVMap：材质纹理坐标（米），烘焙时参与反弹着色
        o.data.materials.clear()
        o.data.materials.append(mats.get(key, mats["_default"]))
        if key not in NO_BAKE:
            bake_objs.append(o)
    lightmap_uvs(bake_objs)

    # 烘焙光照：仅天空（太阳由浏览器实时提供），地面参与遮蔽与反弹
    cr.add_ground(mats["ground"])
    ground = bpy.context.active_object
    cr.setup_world()
    for o in bpy.context.scene.objects:
        if o.type == "LIGHT":
            o.data.energy = 0.0
    cr.setup_render(Path(args.out_glb).resolve().with_suffix(".png"), args.samples, 64, 64)

    images = attach_bake_images(bake_objs)
    bpy.ops.object.select_all(action="DESELECT")
    for o in bake_objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = bake_objs[0]
    bpy.context.scene.render.bake.margin = 4
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"DIRECT", "INDIRECT"}, use_clear=True)

    # 导出：烘焙对象换成「光照图材质」并只留 lightmap UV；其余网格去掉 UV 与材质
    for o in bake_objs:
        o.data.materials.clear()
        o.data.materials.append(lightmap_material(o, images[o.name]))
        for layer in [u for u in o.data.uv_layers if u.name != "lightmap"]:
            o.data.uv_layers.remove(layer)
    for o in meshes:
        if o not in bake_objs:
            o.data.materials.clear()
            while o.data.uv_layers:
                o.data.uv_layers.remove(o.data.uv_layers[0])
    bpy.data.objects.remove(ground, do_unlink=True)
    bpy.ops.object.select_all(action="DESELECT")
    for o in bpy.context.scene.objects:
        o.select_set(o.type == "MESH")
    out_glb = Path(args.out_glb).resolve()
    out_glb.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(out_glb), export_format="GLB", use_selection=True,
                              export_extras=True, export_texcoords=True, export_normals=False,
                              export_materials="EXPORT", export_image_format="WEBP", export_yup=True)
    total_px = sum(img.size[0] * img.size[1] for img in images.values())
    print(f"[bake] {out_glb}（{len(bake_objs)} 个烘焙对象，光照图共 {total_px / 1e6:.1f} 百万像素）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
