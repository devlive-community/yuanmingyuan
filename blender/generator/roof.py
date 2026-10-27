"""roof.py — 屋顶：歇山 / 庑殿 / 攒尖 / 硬山 / 悬山（不含斗拱、瓦面、翼角起翘）。

统一入口 ``build_roof``：按 config 屋顶类型名分派到各生成函数。

庑殿 / 攒尖 / 硬山 / 悬山（简化，见 docs/speculative.md S-038）：
- 庑殿：四坡均按举架折面，各圈等距内收（45° 垂脊，无推山）；正脊方棱同尖山歇山。
- 攒尖：仅四角方亭（面阔 = 进深），四坡收于一点，顶置宝顶（圆柱近似）。
- 硬山：两坡至山墙外皮齐平，山墙为山尖形实心墙体（自台基顶到屋面）。
- 悬山：两坡挑出山面柱中线（出梢），山面柱中线处以山花板封闭。
- 硬山 / 悬山有尖山与卷棚两式，屋脊做法同歇山。

歇山支持两种屋脊：
- 尖山（正脊方棱）：``style="尖山"``（对应 config 屋顶类型「歇山」）；
- 卷棚（无正脊、罗锅圆脊）：``style="卷棚"``（对应「卷棚歇山」，正大光明殿即此式）。

几何构造（均为简化，见 docs/speculative.md S-002…S-006、S-012、S-014）：
- 前后主坡：举架折面（units.juaji_profile），X ∈ [−rx, rx]，
  檐口 (Y = ±半跨, z = 0) 升到屋脊 (Y = 0, z = H)。
- 撒头坡（两山短坡）：水平深取一个步架（S-005，无收山定制），
  从山花底边坡到山面檐口，坡度即檐步五举，与主坡第一步一致。
- 山花：两端垂直三角形，顶点接正脊端、底边接下金檩位高度（S-004）。
- 正脊：尖山式为沿屋脊的方棱，脊高暂取 2 斗口（推测）；
  卷棚式为半圆柱面罗锅脊（半径工作假设 1.5 斗口，S-014），无正脊。
- 四角：三角平板过渡，无冲三翘四起翘（S-006）。
- 主坡两端以垂直三角面封闭（山面端部简化，S-012）。

z 基准：檐口 = 0（调用方传入 z_base = 台基顶 + 柱高，S-002 简化）。
"""

from __future__ import annotations

import math

from generator import mesh as mesh_mod
from generator import units
from generator.plan import PlanGeom

RIDGE_HEIGHT_DOUKOU = 2.0   # 尖山正脊截面高（斗口，推测值）
RIDGE_ROLL_DOUKOU = 1.5     # 卷棚罗锅脊半径（斗口，工作假设，S-014）
ROLL_SEGMENTS = 8           # 罗锅脊圆周分段

SKIRT_OVERHANG_CM = 100.0   # 腰檐（重檐下檐／楼腰檐）外挑（工作假设，S-027）
SKIRT_DROP_CM = 60.0        # 腰檐环带下垂（工作假设，S-027）

XUANSHAN_OVERHANG_DOUKOU = 8.0   # 悬山出梢：屋面挑出山面柱中线（斗口，工作假设，S-038）
GABLE_WALL_OUT_DOUKOU = 6.0      # 硬山山墙外皮距山面柱中（约一柱径，工作假设，S-038）
GABLE_WALL_IN_DOUKOU = 3.0       # 硬山山墙里皮距山面柱中（约半柱径，工作假设，S-038）
FINIAL_RADIUS_DOUKOU = 3.0       # 攒尖宝顶半径（斗口，工作假设，S-038）
FINIAL_HEIGHT_DOUKOU = 6.0       # 攒尖宝顶高（斗口，工作假设，S-038）
FINIAL_SEGMENTS = 12
GABLE_WALL_TOP_DROP_CM = 2.0     # 山墙顶低于屋面，避免与坡面共面闪烁（显示处理，非形制）

# config 屋顶类型名 → (生成类别, 屋脊样式)
ROOF_KINDS: dict[str, tuple[str, str]] = {
    "歇山": ("xieshan", "尖山"),
    "卷棚歇山": ("xieshan", "卷棚"),
    "庑殿": ("wudian", "尖山"),
    "攒尖": ("cuanjian", "尖山"),
    "硬山": ("yingshan", "尖山"),
    "卷棚硬山": ("yingshan", "卷棚"),
    "悬山": ("xuanshan", "尖山"),
    "卷棚悬山": ("xuanshan", "卷棚"),
}

_STYLE_ALIASES = {
    "尖山": "尖山",
    "歇山": "尖山",
    "卷棚": "卷棚",
    "卷棚歇山": "卷棚",
}


def build_roof(
    plan: PlanGeom,
    z_base_cm: float,
    roof_type: str,
    skirts: tuple[float, ...] = (),
    wall_base_cm: float | None = None,
) -> mesh_mod.Mesh:
    """按屋顶类型名生成屋顶网格（统一入口）。

    ``roof_type`` 取 ``ROOF_KINDS`` 的键；``wall_base_cm`` 为硬山山墙底标高
    （一般为台基顶；缺省时山墙只做檐口以上的山尖部分）。
    """
    if roof_type not in ROOF_KINDS:
        raise ValueError(f"未知屋顶类型 {roof_type}，支持 {sorted(ROOF_KINDS)}")
    kind, style = ROOF_KINDS[roof_type]
    if kind == "xieshan":
        return build_roof_xieshan(plan, z_base_cm, style=style, skirts=skirts)
    if kind == "wudian":
        return build_roof_wudian(plan, z_base_cm, skirts=skirts)
    if kind == "cuanjian":
        return build_roof_cuanjian(plan, z_base_cm, skirts=skirts)
    if kind == "yingshan":
        return build_roof_yingshan(plan, z_base_cm, style=style, skirts=skirts, wall_base_cm=wall_base_cm)
    return build_roof_xuanshan(plan, z_base_cm, style=style, skirts=skirts)


def _profile_cm(plan: PlanGeom, n_steps: int) -> list[tuple[float, float]]:
    """举架剖面（cm）：[(自檐口水平内收, 相对檐口升高)]，檐口 → 脊。"""
    d = plan.doukou_cm
    half = plan.eave_width / 2.0
    return [(x * d, y * d) for (x, y) in units.juaji_profile(half / d, n_steps)]


def _profile_z(profile: list[tuple[float, float]], inset: float) -> float:
    """举架剖面上距檐口水平 ``inset`` 处的屋面高（折线插值）。"""
    for (x0, z0), (x1, z1) in zip(profile, profile[1:]):
        if inset <= x1:
            return z0 + (z1 - z0) * (inset - x0) / (x1 - x0)
    return profile[-1][1]


def _hipped_shell(
    profile: list[tuple[float, float]], hx: float, hy: float
) -> mesh_mod.Mesh:
    """四坡屋面（庑殿 / 四角攒尖共用）：檐口矩形 ``2hx × 2hy`` 逐步等距内收。

    第 k 圈为半宽 ``(hx − xk, hy − xk)``、高 ``zk`` 的矩形；短边收至 0 时
    顶圈退化为正脊线段（庑殿）或一点（攒尖），重合顶点合并、退化面降为三角形。
    """
    out = mesh_mod.Mesh()
    index: dict[tuple[float, float, float], int] = {}

    def vid(p: tuple[float, float, float]) -> int:
        key = tuple(round(c, 6) for c in p)
        if key not in index:
            index[key] = len(out.vertices)
            out.vertices.append(p)
        return index[key]

    rings: list[list[int]] = []
    for xk, zk in profile:
        ax, ay = max(hx - xk, 0.0), max(hy - xk, 0.0)
        # 俯视逆时针：前左、前右、后右、后左
        rings.append([vid((-ax, -ay, zk)), vid((ax, -ay, zk)), vid((ax, ay, zk)), vid((-ax, ay, zk))])
    for lo, hi in zip(rings, rings[1:]):
        for i in range(4):
            j = (i + 1) % 4
            face: list[int] = []
            for v in (lo[i], lo[j], hi[j], hi[i]):   # 外法向朝上外（同 box 侧面绕序）
                if v not in face:
                    face.append(v)
            if len(face) >= 3:
                out.faces.append(tuple(face))
    return out


def build_roof_wudian(
    plan: PlanGeom,
    z_base_cm: float,
    n_steps: int = units.DEFAULT_ROOF_STEPS,
    skirts: tuple[float, ...] = (),
) -> mesh_mod.Mesh:
    """庑殿顶（四坡五脊，简化）：四坡均按举架，45° 垂脊、无推山（S-038）。

    须面阔 > 进深（正脊长 = 檐口长 − 檐口宽）；方形平面请用攒尖。
    """
    hx, hy = plan.eave_length / 2.0, plan.eave_width / 2.0
    if hx - hy <= 1e-6:
        raise ValueError("庑殿须面阔大于进深（方形平面请用 攒尖）")
    d = plan.doukou_cm
    profile = _profile_cm(plan, n_steps)
    ridge_z = profile[-1][1]
    roof = _hipped_shell(profile, hx, hy)
    rx = hx - hy                                 # 正脊半长
    ridge_h = RIDGE_HEIGHT_DOUKOU * d
    roof = roof.merged(mesh_mod.box(2.0 * rx + 2.0 * d, 2.0 * d, ridge_z, ridge_z + ridge_h))
    return _finish(plan, roof, z_base_cm, skirts)


def build_roof_cuanjian(
    plan: PlanGeom,
    z_base_cm: float,
    n_steps: int = units.DEFAULT_ROOF_STEPS,
    skirts: tuple[float, ...] = (),
) -> mesh_mod.Mesh:
    """四角攒尖顶（方亭）：四坡按举架收于一点，顶置宝顶（S-038）。

    仅支持面阔 = 进深的方形平面；六角 / 八角攒尖需多边形柱网，暂未实现。
    """
    hx, hy = plan.eave_length / 2.0, plan.eave_width / 2.0
    if abs(hx - hy) > 1e-6 * max(hx, hy):
        raise ValueError(
            f"攒尖暂只支持方形平面（面阔 = 进深），收到 {2 * hx:.1f} × {2 * hy:.1f} cm"
        )
    d = plan.doukou_cm
    profile = _profile_cm(plan, n_steps)
    apex_z = profile[-1][1]
    roof = _hipped_shell(profile, hx, hy)
    roof = roof.merged(
        mesh_mod.cylinder(
            apex_z - d, apex_z + FINIAL_HEIGHT_DOUKOU * d,
            FINIAL_RADIUS_DOUKOU * d, segments=FINIAL_SEGMENTS,
        )
    )
    return _finish(plan, roof, z_base_cm, skirts)


def _gable_slopes(profile: list[tuple[float, float]], half: float, ex: float) -> mesh_mod.Mesh:
    """两坡屋面（硬山 / 悬山）：X ∈ [−ex, ex] 的前后举架折面。"""
    body = mesh_mod.Mesh()
    n_pts = len(profile)
    for sign_y in (-1.0, 1.0):
        base = len(body.vertices)
        for col_x in (-ex, ex):
            for (xk, zk) in profile:
                body.vertices.append((col_x, sign_y * (half - xk), zk))
        for k in range(n_pts - 1):
            i0 = base + k
            i1 = base + n_pts + k
            i2, i3 = i1 + 1, i0 + 1
            if sign_y < 0:
                body.faces.append((i0, i1, i2, i3))
            else:
                body.faces.append((i1, i0, i3, i2))
    return body


def _gable_outline(
    profile: list[tuple[float, float]], half: float, y_edge: float, z_bottom: float,
    drop: float = 0.0,
) -> list[tuple[float, float]]:
    """山面轮廓（YZ 平面）：自 (+y_edge, z_bottom) 起，沿屋面过脊到 (−y_edge, z_bottom)。

    ``y_edge`` 处屋面高按举架插值，屋面线整体下移 ``drop``；
    轮廓相对底边中点 (0, z_bottom) 星形可见（举架下凸），可自该点扇形三角化。
    """
    inset0 = half - y_edge
    pts: list[tuple[float, float]] = [(y_edge, z_bottom), (y_edge, _profile_z(profile, inset0) - drop)]
    pts += [(half - xk, zk - drop) for (xk, zk) in profile if xk > inset0 + 1e-6]
    upper = pts[1:]
    pts += [(-y, z) for (y, z) in reversed(upper[:-1])]
    pts.append((-y_edge, z_bottom))
    return pts


def _gable_slab(outline: list[tuple[float, float]], z_bottom: float, x0: float, x1: float) -> mesh_mod.Mesh:
    """山面轮廓沿 X 挤出为实心体（x0 < x1）；两端面自底边中点扇形三角化。"""
    n = len(outline)
    verts: list[tuple[float, float, float]] = (
        [(x0, y, z) for (y, z) in outline] + [(x1, y, z) for (y, z) in outline]
        + [(x0, 0.0, z_bottom), (x1, 0.0, z_bottom)]
    )
    c0, c1 = 2 * n, 2 * n + 1
    faces: list[tuple[int, ...]] = []
    for i in range(n - 1):
        faces.append((c1, n + i, n + i + 1))      # +X 端面
        faces.append((c0, i + 1, i))              # −X 端面
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))        # 侧面（含底面），外法向朝外
    return mesh_mod.Mesh(vertices=verts, faces=faces)


def _gable_board(outline: list[tuple[float, float]], z_bottom: float, x: float) -> mesh_mod.Mesh:
    """山花板：x 处的竖直山面轮廓薄面（法向 +X），自底边中点扇形三角化。"""
    n = len(outline)
    verts = [(x, y, z) for (y, z) in outline] + [(x, 0.0, z_bottom)]
    return mesh_mod.Mesh(vertices=verts, faces=[(n, i, i + 1) for i in range(n - 1)])


def _gable_ridge(style: str, ex: float, ridge_z: float, d: float) -> mesh_mod.Mesh:
    if style == "尖山":
        return mesh_mod.box(2.0 * ex, 2.0 * d, ridge_z, ridge_z + RIDGE_HEIGHT_DOUKOU * d)
    return _round_ridge(ex, ridge_z, RIDGE_ROLL_DOUKOU * d, ROLL_SEGMENTS)


def build_roof_yingshan(
    plan: PlanGeom,
    z_base_cm: float,
    n_steps: int = units.DEFAULT_ROOF_STEPS,
    style: str = "尖山",
    skirts: tuple[float, ...] = (),
    wall_base_cm: float | None = None,
) -> mesh_mod.Mesh:
    """硬山顶：两坡止于山墙外皮，山墙为山尖形实心墙（S-038）。

    ``wall_base_cm`` 给定时山墙自该标高（台基顶）砌起，否则只做檐口以上山尖。
    """
    style = _STYLE_ALIASES.get(style)
    if style is None:
        raise ValueError(f"未知屋脊样式，支持 {sorted(_STYLE_ALIASES)}")
    d = plan.doukou_cm
    half = plan.eave_width / 2.0
    profile = _profile_cm(plan, n_steps)
    x_out = plan.length / 2.0 + GABLE_WALL_OUT_DOUKOU * d
    x_in = plan.length / 2.0 - GABLE_WALL_IN_DOUKOU * d
    y_wall = plan.width / 2.0 + GABLE_WALL_OUT_DOUKOU * d
    z_wall = 0.0 if wall_base_cm is None else wall_base_cm - z_base_cm
    if z_wall > 0.0:
        raise ValueError("山墙底标高须不高于檐口")

    roof = _gable_slopes(profile, half, x_out)
    outline = _gable_outline(profile, half, y_wall, z_wall, drop=GABLE_WALL_TOP_DROP_CM)
    wall = _gable_slab(outline, z_wall, x_in, x_out)
    roof = roof.merged(wall).merged(wall.mirrored("x"))
    roof = roof.merged(_gable_ridge(style, x_out, profile[-1][1], d))
    return _finish(plan, roof, z_base_cm, skirts)


def build_roof_xuanshan(
    plan: PlanGeom,
    z_base_cm: float,
    n_steps: int = units.DEFAULT_ROOF_STEPS,
    style: str = "尖山",
    skirts: tuple[float, ...] = (),
) -> mesh_mod.Mesh:
    """悬山顶：两坡挑出山面柱中线一个出梢，柱中线处以山花板封闭（S-038）。"""
    style = _STYLE_ALIASES.get(style)
    if style is None:
        raise ValueError(f"未知屋脊样式，支持 {sorted(_STYLE_ALIASES)}")
    d = plan.doukou_cm
    half = plan.eave_width / 2.0
    profile = _profile_cm(plan, n_steps)
    ex = plan.length / 2.0 + XUANSHAN_OVERHANG_DOUKOU * d

    roof = _gable_slopes(profile, half, ex)
    board = _gable_board(_gable_outline(profile, half, plan.width / 2.0, 0.0), 0.0, plan.length / 2.0)
    roof = roof.merged(board).merged(board.mirrored("x"))
    roof = roof.merged(_gable_ridge(style, ex, profile[-1][1], d))
    return _finish(plan, roof, z_base_cm, skirts)


def _finish(plan: PlanGeom, roof: mesh_mod.Mesh, z_base_cm: float, skirts: tuple[float, ...]) -> mesh_mod.Mesh:
    """抬升到檐口标高并追加腰檐环带。"""
    roof = roof.translated(dz=z_base_cm)
    for z in skirts:
        roof = roof.merged(_skirt_ring(plan, float(z)))
    return roof


def build_roof_xieshan(
    plan: PlanGeom,
    z_base_cm: float,
    n_steps: int = units.DEFAULT_ROOF_STEPS,
    style: str = "尖山",
    skirts: tuple[float, ...] = (),
) -> mesh_mod.Mesh:
    """生成简化歇山顶网格（cm）。``z_base_cm`` 为檐口标高（台基顶 + 檐柱高）。

    ``style``：尖山（有正脊方棱）或 卷棚（罗锅圆脊，无正脊）。
    ``skirts``：腰檐环带的绝对标高层（重檐下檐／楼腰檐，S-027）。
    """
    style = _STYLE_ALIASES.get(style)
    if style is None:
        raise ValueError(f"未知屋脊样式，支持 {sorted(_STYLE_ALIASES)}")
    d = plan.doukou_cm
    half = plan.eave_width / 2.0                 # 半跨（cm）：檐口到脊的水平距
    profile = [
        (x * d, y * d)
        for (x, y) in units.juaji_profile(half / d, n_steps)
    ]
    s1, y1 = profile[1]                          # 第一步末（下金位）：撒头水平深 / 山花底高
    ridge_z = profile[-1][1]                     # 脊高（相对檐口）
    l2e = plan.eave_length / 2.0                 # 檐口半长（含上檐出）
    rx = l2e - s1                                # 正脊半长 = 主坡 X 半宽
    ty = half - s1                               # 山花底边 Y 半宽（下金檩位）

    # ---- 前后主坡（举架折面，绕序使外法向朝上外） ----
    body = mesh_mod.Mesh()
    for sign_y in (-1.0, 1.0):
        base = len(body.vertices)
        n_pts = len(profile)
        for col_x in (-rx, rx):
            for (xk, yk) in profile:
                body.vertices.append((col_x, sign_y * (half - xk), yk))
        for k in range(n_pts - 1):
            i0 = base + k          # X=−rx 列第 k 点（靠檐口）
            i1 = base + n_pts + k  # X=+rx 列第 k 点
            i2, i3 = i1 + 1, i0 + 1
            if sign_y < 0:         # 前坡（−Y 侧）
                body.faces.append((i0, i1, i2, i3))
            else:                  # 后坡（+Y 侧）
                body.faces.append((i1, i0, i3, i2))

    # ---- 右端件（+X）：撒头坡、山花、主坡两端端部封闭，整体镜像出左端 ----
    right = mesh_mod.Mesh(
        vertices=[
            (rx, -ty, y1), (rx, ty, y1), (l2e, half, 0.0), (l2e, -half, 0.0),  # 撒头坡（平面梯形）
            (rx, -ty, y1), (rx, ty, y1), (rx, 0.0, ridge_z),                    # 山花（垂直三角）
            (rx, ty, 0.0), (rx, half, 0.0), (rx, ty, y1),                       # 端部封闭·后坡侧
            (rx, -ty, y1), (rx, -half, 0.0), (rx, -ty, 0.0),                    # 端部封闭·前坡侧
        ],
        faces=[
            (0, 3, 2, 1),   # 撒头坡，外法向 +X（已验证绕序）
            (3, 4, 5),      # 山花，外法向 +X（顶点接脊端）
            (7, 8, 9),      # 端部封闭（后坡侧），外法向 +X
            (10, 11, 12),   # 端部封闭（前坡侧），外法向 +X
        ],
    )
    roof = body.merged(right).merged(right.mirrored("x"))

    # ---- 四角过渡（三角平板，无起翘 S-006）：以前右角为基准，镜像出四角 ----
    corner = mesh_mod.Mesh(
        vertices=[(rx, -half, 0.0), (l2e, -half, 0.0), (rx, -ty, y1)],
        faces=[(0, 1, 2)],  # 外法向朝 −Y（前外，已验证绕序）
    )
    roof = (
        roof.merged(corner)
        .merged(corner.mirrored("x"))
        .merged(corner.mirrored("y"))
        .merged(corner.mirrored("x").mirrored("y"))
    )

    # ---- 屋脊 ----
    if style == "尖山":
        ridge_h = RIDGE_HEIGHT_DOUKOU * d
        roof = roof.merged(mesh_mod.box(2.0 * rx, 2.0 * d, ridge_z, ridge_z + ridge_h))
    else:  # 卷棚：半圆柱面罗锅脊
        roll_r = RIDGE_ROLL_DOUKOU * d
        roof = roof.merged(_round_ridge(rx, ridge_z, roll_r, ROLL_SEGMENTS))

    roof = roof.translated(dz=z_base_cm)
    for z in skirts:
        roof = roof.merged(_skirt_ring(plan, float(z)))
    return roof


def _skirt_ring(plan: PlanGeom, z_hi: float) -> mesh_mod.Mesh:
    """腰檐环带：沿柱网外圈的四坡薄檐（重檐下檐／楼腰檐，S-027）。"""
    hl, hw = plan.length / 2.0, plan.width / 2.0
    o, drop = SKIRT_OVERHANG_CM, SKIRT_DROP_CM
    verts = [
        (-hl, -hw, z_hi), (hl, -hw, z_hi), (hl, hw, z_hi), (-hl, hw, z_hi),
        (-hl - o, -hw - o, z_hi - drop), (hl + o, -hw - o, z_hi - drop),
        (hl + o, hw + o, z_hi - drop), (-hl - o, hw + o, z_hi - drop),
    ]
    faces = [
        (0, 1, 5, 4),  # 南
        (1, 2, 6, 5),  # 东
        (2, 3, 7, 6),  # 北
        (3, 0, 4, 7),  # 西
    ]
    return mesh_mod.Mesh(vertices=[tuple(v) for v in verts], faces=[tuple(f) for f in faces])


def _round_ridge(half_len: float, z_c: float, radius: float, segments: int) -> mesh_mod.Mesh:
    """卷棚罗锅脊：沿 X 轴的半圆柱面（上半圆），两端半圆封口。"""
    if segments < 3:
        raise ValueError("罗锅脊 segments 至少为 3")
    verts: list[tuple[float, float, float]] = []
    for x in (-half_len, half_len):
        for k in range(segments + 1):
            a = math.pi * k / segments
            verts.append((x, radius * math.cos(a), z_c + radius * math.sin(a)))
    n = segments + 1
    faces: list[tuple[int, ...]] = []
    for k in range(segments):
        # 条带：a=(−L,φk) b=(−L,φk+1) c=(+L,φk+1) d=(+L,φk)，外法向朝外
        faces.append((k, k + 1, n + k + 1, n + k))
    cx_right = len(verts)
    verts.append((half_len, 0.0, z_c))
    for k in range(segments):
        faces.append((cx_right, n + k, n + k + 1))          # +X 端封口，法向 +X
    cx_left = len(verts)
    verts.append((-half_len, 0.0, z_c))
    for k in range(segments):
        faces.append((cx_left, k + 1, k))                    # −X 端封口，法向 −X
    return mesh_mod.Mesh(vertices=verts, faces=faces)
