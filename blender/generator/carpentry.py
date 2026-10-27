"""carpentry.py — 檐枋、墙体与门窗装修（小木作：槅扇、槛窗、板门）。

围护形式（``enclosure``，见 config.BuildingParams）：
- ``open``     敞：亭、敞阁，只有檐枋，无墙无装修；
- ``front``    前檐装修（缺省）：前檐明间槅扇门、其余槛窗；两山山墙、后檐墙；
- ``surround`` 四面装修：榭、水阁等，四面槛窗，前后檐明间槅扇门；
- ``gate``     门殿：前后檐中间（五间以上为中三间）板门，其余为墙。

``corridor = surround``（周围廊）时，墙与装修退到内圈金柱一线，外圈檐柱成廊。
楼（stories = 2）的上层一律以槛窗代门。

构件（网格标签末段 = 材质类）：
- ``beams``     檐枋（额枋）：每间柱头之间一根，青绿彩画占位色；
- ``red_wall``  墙上身（红灰抹面）；
- ``wall_base`` 下碱与槛墙（青砖）；
- ``joinery``   槛框、槅扇 / 槛窗的边梃抹头、裙板绦环、棂心、板门（朱红油饰）；
- ``paper``     棂心背后的窗户纸（高丽纸）。

比例出处见 units.py「墙体与装修」一节；棂心纹样（正方格）、扇数规则、
墙厚与柱子全包在墙内等为简化，见 speculative S-042。

局部坐标：每段墙沿 u 轴（局部 X）展开，正面朝 −v（局部 −Y）；
生成后按所在一面绕 Z 旋转、平移到柱中线。
"""

from __future__ import annotations

from generator import mesh as mesh_mod
from generator import units
from generator.plan import PlanGeom

ENCLOSURES = ("open", "front", "surround", "gate")
CORRIDORS = ("none", "surround")

COMPONENTS = ("beams", "red_wall", "wall_base", "joinery", "paper")

LEAF_THICK_CM = 6.0          # 槅扇 / 槛窗扇厚（工作假设，S-042）
STILE_SHARE = 0.1            # 边梃宽 ≈ 扇宽 1/10（工作假设，S-042）
BAR_CM = 2.4                 # 棂条看面宽（工作假设，S-042）
LATTICE_COLS = 3             # 正方格棂心：每扇横向 3 格（纹样为占位，S-042）
PAPER_CM = 0.6               # 窗纸厚（几何占位）
LEAF_MAX_CM = 110.0          # 单扇最大宽：超出则增加扇数（4 → 6，工作假设，S-042）

# 每一面的朝向：(绕 Z 旋转角, 柱中线法向坐标取 −/+ 半宽)；局部 −v 朝外
_SIDES = {
    "front": 0.0,     # −Y
    "back": 180.0,    # +Y
    "left": -90.0,    # −X
    "right": 90.0,    # +X
}


def _box(u0: float, u1: float, v0: float, v1: float, z0: float, z1: float) -> mesh_mod.Mesh:
    return mesh_mod.box(u1 - u0, v1 - v0, z0, z1, cx=(u0 + u1) / 2.0, cy=(v0 + v1) / 2.0)


class _Parts:
    """按材质类累积网格。"""

    def __init__(self) -> None:
        self.meshes = {c: mesh_mod.Mesh() for c in COMPONENTS}

    def add(self, comp: str, m: mesh_mod.Mesh) -> None:
        self.meshes[comp] = self.meshes[comp].merged(m)


def _bay_kinds(enclosure: str, side: str, n_bays: int, upper: bool) -> list[str]:
    """一面墙各间的填充：wall / door / window / gate。"""
    mid = n_bays // 2
    centre = {mid - 1, mid, mid + 1} if n_bays >= 5 else {mid}
    kinds: list[str] = []
    for i in range(n_bays):
        if enclosure == "gate":
            k = "gate" if side in ("front", "back") and i in centre else "wall"
        elif enclosure == "surround":
            k = "door" if side in ("front", "back") and i == mid else "window"
        else:  # front
            k = ("door" if i == mid else "window") if side == "front" else "wall"
        if upper and k in ("door", "gate"):
            k = "window"
        kinds.append(k)
    return kinds


def _leaf_count(clear_cm: float) -> int:
    """每间扇数：偶数，单扇宽不超过 LEAF_MAX_CM（常见四扇，宽明间六扇）。"""
    n = 2
    while clear_cm / n > LEAF_MAX_CM:
        n += 2
    return n


def _leaf(parts: _Parts, u0: float, u1: float, z0: float, z1: float, door: bool) -> None:
    """一扇槅扇（door）或槛窗扇：边梃、抹头、正方格棂心、窗纸；槅扇另有绦环板与裙板。"""
    t = LEAF_THICK_CM / 2.0
    w = u1 - u0
    s = max(4.0, w * STILE_SHARE)
    parts.add("joinery", _box(u0, u0 + s, -t, t, z0, z1))              # 边梃
    parts.add("joinery", _box(u1 - s, u1, -t, t, z0, z1))
    h = z1 - z0
    if door:
        zl = z0 + h * (1.0 - units.LATTICE_SHARE)                       # 槅心下抹头
        zp = z0 + (zl - z0) * 0.78                                      # 裙板上抹头（其上为绦环板）
        for za, zb in ((z0, z0 + s), (zp, zp + s * 0.7), (zl - s, zl), (z1 - s, z1)):
            parts.add("joinery", _box(u0 + s, u1 - s, -t, t, za, zb))   # 抹头
        parts.add("joinery", _box(u0 + s, u1 - s, -t * 0.4, t * 0.4, z0 + s, zl - s))  # 裙板、绦环板（凹入）
    else:
        zl = z0 + s
        for za, zb in ((z0, z0 + s), (z1 - s, z1)):
            parts.add("joinery", _box(u0 + s, u1 - s, -t, t, za, zb))
    _lattice(parts, u0 + s, u1 - s, zl, z1 - s, t)


def _lattice(parts: _Parts, u0: float, u1: float, z0: float, z1: float, t: float) -> None:
    """正方格棂心 + 背后窗纸。"""
    if u1 - u0 <= 2 * BAR_CM or z1 - z0 <= 2 * BAR_CM:
        return
    cell = (u1 - u0) / LATTICE_COLS
    rows = max(1, round((z1 - z0) / cell))
    b = BAR_CM / 2.0
    for k in range(1, LATTICE_COLS):
        u = u0 + k * cell
        parts.add("joinery", _box(u - b, u + b, -t * 0.6, t * 0.2, z0, z1))
    ch = (z1 - z0) / rows
    for k in range(1, rows):
        z = z0 + k * ch
        parts.add("joinery", _box(u0, u1, -t * 0.6, t * 0.2, z - b, z + b))
    parts.add("paper", _box(u0, u1, t * 0.2, t * 0.2 + PAPER_CM, z0, z1))


def _frame(parts: _Parts, a: float, b: float, z0: float, z_open: float, d: float) -> tuple[float, float, float, float]:
    """槛框：下槛、抱框、中槛、横披（棂心）、上槛。返回门窗扇所在的 (u0, u1, 下沿, 上沿)。"""
    t = LEAF_THICK_CM * 0.75
    rail = units.RAIL_PER_DIAMETER * d
    sill = units.LOWER_SILL_PER_DIAMETER * d
    parts.add("joinery", _box(a, a + rail, -t, t, z0, z_open))          # 抱框
    parts.add("joinery", _box(b - rail, b, -t, t, z0, z_open))
    u0, u1 = a + rail, b - rail
    parts.add("joinery", _box(u0, u1, -t, t, z_open - rail, z_open))    # 上槛
    z_mid = z_open - rail - (z_open - z0) * units.TRANSOM_PER_OPENING
    parts.add("joinery", _box(u0, u1, -t, t, z_mid - rail, z_mid))      # 中槛
    _lattice(parts, u0, u1, z_mid, z_open - rail, LEAF_THICK_CM / 2.0)  # 横披窗
    return u0, u1, z0 + sill, z_mid - rail


def _fill_bay(parts: _Parts, kind: str, a: float, b: float, z0: float, z_beam: float,
              plan: PlanGeom) -> None:
    """一间（柱中 a → b，地面 z0 → 枋底 z_beam）的墙或装修。"""
    d = plan.eave_column_diameter_cm
    h = plan.column_height_cm
    r = d / 2.0
    if kind == "wall":
        wt = units.WALL_THICK_PER_DIAMETER * d / 2.0
        zb = min(z_beam, z0 + units.WALL_BASE_PER_COLUMN_HEIGHT * h)
        p = units.WALL_BASE_PROUD_CM
        parts.add("wall_base", _box(a, b, -wt - p, wt + p, z0, zb))   # 下碱
        parts.add("red_wall", _box(a, b, -wt, wt, zb, z_beam))         # 上身
        return
    a, b = a + r, b - r                                                # 门窗在柱间净宽内
    if kind == "window":
        zs = z0 + units.SILL_WALL_PER_COLUMN_HEIGHT * h
        wt = units.BEAM_THICK_PER_DIAMETER * d / 2.0
        parts.add("wall_base", _box(a, b, -wt, wt, z0, zs - 6.0))     # 槛墙
        parts.add("joinery", _box(a - 2.0, b + 2.0, -wt - 3.0, wt + 3.0, zs - 6.0, zs))  # 榻板
        u0, u1, zl, zt = _frame(parts, a, b, zs, z_beam, d)
        zl = zs + units.RAIL_PER_DIAMETER * d * 0.6                   # 风槛（矮于下槛）
        parts.add("joinery", _box(u0, u1, -LEAF_THICK_CM * 0.75, LEAF_THICK_CM * 0.75, zs, zl))
    else:
        u0, u1, zl, zt = _frame(parts, a, b, z0, z_beam, d)
        parts.add("joinery", _box(u0, u1, -LEAF_THICK_CM * 0.75, LEAF_THICK_CM * 0.75, z0, zl))  # 下槛
    if kind == "gate":                                                 # 板门：两扇实心门板
        mid = (u0 + u1) / 2.0
        for ua, ub in ((u0, mid - 0.5), (mid + 0.5, u1)):
            parts.add("joinery", _box(ua, ub, -LEAF_THICK_CM, LEAF_THICK_CM / 2.0, zl, zt))
        return
    n = _leaf_count(u1 - u0)
    lw = (u1 - u0) / n
    for k in range(n):
        _leaf(parts, u0 + k * lw, u0 + (k + 1) * lw, zl, zt, door=(kind == "door"))


def _ring(plan: PlanGeom, inset: int) -> dict[str, tuple[float, list[float]]]:
    """一圈柱中线：每面 (法向坐标的绝对值, 沿墙方向的分位线)。inset = 1 为内圈金柱一线。"""
    xs = plan.x_lines[inset:len(plan.x_lines) - inset]
    ys = plan.y_lines[inset:len(plan.y_lines) - inset]
    hx, hy = xs[-1], ys[-1]
    return {"front": (hy, xs), "back": (hy, xs), "left": (hx, ys), "right": (hx, ys)}


def _place(m: mesh_mod.Mesh, side: str, offset: float) -> mesh_mod.Mesh:
    """局部（沿 u 展开、柱中线在 v = 0）→ 平面坐标：先移到 −offset，再按该面旋转。"""
    return m.translated(dy=-offset).rotated_z(_SIDES[side])


def build_enclosure(plan: PlanGeom, platform_top_cm: float, stories: int = 1,
                    enclosure: str = "front", corridor: str = "none",
                    gable_walls: bool = False) -> list[tuple[str, mesh_mod.Mesh]]:
    """生成檐枋、墙体与门窗装修，按材质类返回 [(构件 id, Mesh)]（空构件省略）。

    ``gable_walls``：屋顶模块已砌山墙（硬山），两山不再填墙。

    各层：地面 = 台基顶 + 柱高 × (层号 − 1)，枋顶 = 该层柱顶；
    分位线左右对称，故旋转到后檐 / 两山时间序反向不影响结果。
    """
    if enclosure not in ENCLOSURES:
        raise ValueError(f"enclosure 须为 {ENCLOSURES} 之一，收到 {enclosure}")
    if corridor not in CORRIDORS:
        raise ValueError(f"corridor 须为 {CORRIDORS} 之一，收到 {corridor}")
    inset = 1 if corridor == "surround" else 0
    if inset and (plan.n_bays < 3 or plan.n_depth_bays < 3):
        raise ValueError("周围廊须面阔、进深均 ≥ 3 间")
    parts = _Parts()
    d = plan.eave_column_diameter_cm
    beam_h = units.BEAM_HEIGHT_PER_DIAMETER * d
    beam_t = units.BEAM_THICK_PER_DIAMETER * d / 2.0
    rings = [_ring(plan, 0)] + ([_ring(plan, 1)] if inset else [])
    for story in range(max(1, int(stories))):
        z0 = platform_top_cm + plan.column_height_cm * story
        z_top = z0 + plan.column_height_cm
        for ring in rings:                                               # 檐枋（及廊内金枋）
            for side, (off, lines) in ring.items():
                local = mesh_mod.Mesh()
                for a, b in zip(lines, lines[1:]):
                    local = local.merged(_box(a, b, -beam_t, beam_t, z_top - beam_h, z_top))
                parts.add("beams", _place(local, side, off))
        if enclosure == "open":
            continue
        for side, (off, lines) in rings[-1].items():
            if gable_walls and side in ("left", "right") and enclosure != "surround":
                continue
            local = _Parts()
            kinds = _bay_kinds(enclosure, side, len(lines) - 1, upper=story > 0)
            for (a, b), kind in zip(zip(lines, lines[1:]), kinds):
                _fill_bay(local, kind, a, b, z0, z_top - beam_h, plan)
            for comp, m in local.meshes.items():
                if m.vertices:
                    parts.add(comp, _place(m, side, off))
    return [(c, m) for c, m in parts.meshes.items() if m.vertices]
