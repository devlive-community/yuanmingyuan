"""scene.py — 景群装配：多栋建筑按方位关系摆放（纯函数，无 bpy）。

输入：config.Scene（场景 YAML 解析结果）+ 场景文件路径（用于解析相对 ref）。
输出：``[(标签, Mesh)]``。标签只用英文标识，以 ``/`` 分段：
``{建筑 key}/{构件}``（如 ``peidian_wuying_2/roof``），总园再前缀景 id
（``zhengda_guangming/peidian_wuying_2/roof``）。建筑 key 取建筑 YAML 的 id，
同景重复引用时依次加 ``_2``、``_3``。中文名称只在页面渲染时按 id 查表显示。

史料边界：方位关系（谁在谁东/西/南）以记载为准；**间距尺寸无记载，为工作假设**
（speculative S-018），全部写在场景 YAML 中并逐条注明。
"""

from __future__ import annotations

from pathlib import Path

from generator import bridges
from generator import haiyantang_reference
from generator import config as config_mod
from generator import mesh as mesh_mod
from generator import terrain as terrain_mod
from generator import western
from generator.assemble import build_building_parts


# 专属场景构建器（不走 building/scene YAML 参数体系，如西洋楼体量骨架）
_SPECIAL_BUILDERS = {
    "haiyantang": western.build_haiyantang_scene,
    "haiyantang_reference": haiyantang_reference.build_haiyantang_reference_scene,
    "yuanyingguan_dashuifa": western.build_yuanyingguan_dashuifa_scene,
    "jiajing_mingqin": bridges.build_jiajing_mingqin_scene,
    "quyuan_fenghe": bridges.build_quyuan_fenghe_scene,
}


def resolve_ref(scene_path: str | Path, ref: str) -> Path:
    """解析场景 YAML 中的建筑 ref（相对场景文件目录）。"""
    p = Path(ref)
    if p.is_absolute():
        return p
    return (Path(scene_path).resolve().parent / p)


def building_keys(
    scene: config_mod.Scene, scene_path: str | Path
) -> list[tuple[str, config_mod.SceneBuilding, Path]]:
    """逐栋返回 (建筑 key, 场景条目, 建筑 YAML 路径)；key = 建筑 id，重复时加 _2、_3…"""
    seen: dict[str, int] = {}
    out: list[tuple[str, config_mod.SceneBuilding, Path]] = []
    for sb in scene.buildings:
        path = resolve_ref(scene_path, sb.ref)
        bid = config_mod.load_building(path).id
        seen[bid] = seen.get(bid, 0) + 1
        out.append((bid if seen[bid] == 1 else f"{bid}_{seen[bid]}", sb, path))
    return out


def build_scene(
    scene: config_mod.Scene, scene_path: str | Path
) -> list[tuple[str, mesh_mod.Mesh]]:
    """组装景群：逐栋生成 → 绕 Z 旋转 → 平移到位。"""
    if scene.special:
        builder = _SPECIAL_BUILDERS.get(scene.special)
        if builder is None:
            raise ValueError(f"未注册的专属场景构建器: {scene.special}")
        return builder()
    out: list[tuple[str, mesh_mod.Mesh]] = []
    for key, sb, path in building_keys(scene, scene_path):
        parts, _pl = build_building_parts(config_mod.load_building(path))
        for comp, m in parts:
            placed = m.rotated_z(sb.rotation_deg).translated(dx=sb.x_cm, dy=sb.y_cm)
            out.append((f"{key}/{comp}", placed))
    if scene.island_w_cm > 0 and scene.island_d_cm > 0:
        # 岛台：湖心岛地面（顶面 z=30，略高于总园湖面 0.6；建筑台基坐其上，S-030）
        xs: list[float] = []
        ys: list[float] = []
        for _label, m in out:
            (bx0, by0, _), (bx1, by1, _) = m.bounds()
            xs += [bx0, bx1]
            ys += [by0, by1]
        cx, cy = (max(xs) + min(xs)) / 2.0, (max(ys) + min(ys)) / 2.0
        w = max(scene.island_w_cm, (max(xs) - min(xs)) * 1.15)
        d = max(scene.island_d_cm, (max(ys) - min(ys)) * 1.15)
        out = [("island", mesh_mod.box(w, d, 0.0, 30.0, cx=cx, cy=cy))] + out
    if scene.water:
        out = [("water", _water_plane(out))] + out
    return out


def _water_plane(parts: list[tuple[str, mesh_mod.Mesh]]) -> mesh_mod.Mesh:
    """示意水面：覆盖全部建筑的平面盒体（z −30…0，台基坐于水面，S-021）。"""
    xs: list[float] = []
    ys: list[float] = []
    for _label, m in parts:
        (x0, y0, _), (x1, y1, _) = m.bounds()
        xs += [x0, x1]
        ys += [y0, y1]
    pad = max(600.0, 0.2 * max(max(xs) - min(xs), max(ys) - min(ys)))
    return mesh_mod.box(
        (max(xs) - min(xs)) + 2.0 * pad,
        (max(ys) - min(ys)) + 2.0 * pad,
        -30.0,
        0.0,
        cx=(max(xs) + min(xs)) / 2.0,
        cy=(max(ys) + min(ys)) / 2.0,
    )


def build_garden(
    garden: config_mod.Garden, garden_path: str | Path
) -> list[tuple[str, mesh_mod.Mesh]]:
    """总园装配：逐景（或嵌套子园）平移到园区坐标，再加示意湖面矩形。

    湖面顶面 z 取 0.6 cm（高于景内示意水面的 0），避免共面闪烁；
    6 mm 在数十米尺度不可见（S-022）。
    scenes 项的 ref 可指向场景文件（scene 节）或另一个总园文件（garden 节，递归）。
    """
    out: list[tuple[str, mesh_mod.Mesh]] = []
    for gs in garden.scenes:
        sp = resolve_ref(garden_path, gs.ref)
        kind = config_mod.peek_kind(sp)
        if kind == "garden":
            sub = config_mod.load_garden(sp)
            sub_parts = build_garden(sub, sp)
        else:
            sc = config_mod.load_scene(sp)
            sub_parts = [(f"{sc.id}/{label}", m) for label, m in build_scene(sc, sp)]
            sub = None
        for label, m in sub_parts:
            placed = m.rotated_z(gs.rotation_deg) if gs.rotation_deg else m
            full = f"{sub.id}/{label}" if sub is not None else label
            out.append((full, placed.translated(dx=gs.x_cm, dy=gs.y_cm)))
    for i, lk in enumerate(garden.lakes):
        if lk.polygon:
            pts = terrain_mod.POLYGONS.get(lk.polygon)
            if pts is None:
                raise ValueError(
                    f"未知湖面多边形: {lk.polygon}（可用: {sorted(terrain_mod.POLYGONS)}）"
                )
            plate = terrain_mod.polygon_slab(
                [(x + lk.x_cm, y + lk.y_cm) for (x, y) in pts], z_top=0.6
            )
        else:
            plate = mesh_mod.box(lk.w_cm, lk.d_cm, -30.0, 0.6, cx=lk.x_cm, cy=lk.y_cm)
        out.append((f"{lk.polygon or f'lake_{i + 1}'}/water", plate))
    if garden.terrain is not None:
        tg = garden.terrain
        polys = terrain_mod.load_polygons(resolve_ref(garden_path, tg.file), tg.names)
        if not polys:
            raise ValueError(f"terrain 未匹配到任何水域: {tg.file} / {tg.names}")
        for p in polys:
            out.append((f"{p['id']}/water", terrain_mod.polygon_slab(p["coords_cm"], z_top=0.6)))
    return out
