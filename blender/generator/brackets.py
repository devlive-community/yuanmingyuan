"""brackets.py — 斗拱层（简化）：平板枋 + 柱头科 / 平身科 / 角科 + 挑檐枋。

比例出处与推测项（docs/sources/sources.md、docs/speculative.md S-040）：
- 每一拽架（出一跳）3 斗口：units.TIAO_DOUKOU（《清式营造则例》归纳值，medium）。
- 出跳数：一斗三升 0、三踩 1、五踩 2、七踩 3、九踩 4（踩数 = 2 × 出跳 + 1，通例）。
- 有斗拱时上檐出 = 出踩 + 21 斗口（自挑檐桁中起算，见 units.UPPER_EAVE_PROJECTION_DOUKOU）。
- 以下均为工作假设（S-040）：平板枋高 2 / 宽 3.5 斗口；每层（坐斗、各跳、撑头木）高 2 斗口，
  斗拱层高 = 2 × (出跳数 + 2) 斗口；坐斗 3 × 3 斗口；栱、翘宽 1.25 斗口；
  横栱长 6.2 斗口（瓜栱）/ 7.2 斗口（厢栱）；平身科按攒档 11 斗口在各间内均分；
  角科以两向柱头科叠合近似（无斜出角翘、角昂）。
- 每攒以逐层外伸的实心盒体堆叠近似，里外拽对称；不做昂嘴、栱瓣、升斗细部。

坐标同 plan：X 面阔、Y 进深、正面朝 −Y；z 为绝对标高（cm）。
"""

from __future__ import annotations

import re

from generator import mesh as mesh_mod
from generator import units
from generator.plan import PlanGeom

PLATE_HEIGHT_DOUKOU = 2.0     # 平板枋高（工作假设，S-040）
PLATE_WIDTH_DOUKOU = 3.5      # 平板枋宽（工作假设，S-040）
LEVEL_HEIGHT_DOUKOU = 2.0     # 斗拱每层高（足材，工作假设，S-040）
SEAT_DOUKOU = 3.0             # 坐斗见方（工作假设，S-040）
ARM_WIDTH_DOUKOU = 1.25       # 栱 / 翘宽（工作假设，S-040）
GUA_GONG_DOUKOU = 6.2         # 瓜栱（横栱）长（工作假设，S-040）
XIANG_GONG_DOUKOU = 7.2       # 厢栱长（挑檐处横栱，工作假设，S-040）
FANG_WIDTH_DOUKOU = 1.0       # 挑檐枋宽（工作假设，S-040）

_CN_DIGITS = {"三": 3, "五": 5, "七": 7, "九": 9}


def tiao_count(bracket_set: str) -> int:
    """由斗拱名称取出跳数：一斗三升 → 0；N 踩 → (N − 1) / 2（如 五踩重昂 → 2）。"""
    s = bracket_set.strip()
    if s.startswith("一斗三升"):
        return 0
    m = re.match(r"^([三五七九])踩", s)
    if not m:
        raise ValueError(f"无法识别斗拱名称 {bracket_set!r}（应以 一斗三升 或 三/五/七/九踩 开头）")
    return (_CN_DIGITS[m.group(1)] - 1) // 2


def projection_cm(doukou_cm: float, tiao: int) -> float:
    """斗拱出踩（正心至挑檐中水平距）= 出跳数 × 拽架。"""
    return tiao * units.TIAO_DOUKOU * doukou_cm


def layer_height_cm(doukou_cm: float, tiao: int) -> float:
    """斗拱层总高（柱顶至挑檐枋顶）= 平板枋 + 坐斗 + 各跳 + 撑头木（S-040）。"""
    return (PLATE_HEIGHT_DOUKOU + LEVEL_HEIGHT_DOUKOU * (tiao + 2)) * doukou_cm


def _set_positions(lines: list[float], d: float) -> list[float]:
    """一面檐上各攒位置：柱头（含角）+ 各间内按攒档 11 斗口均分的平身科（S-040）。"""
    out = [lines[0]]
    for a, b in zip(lines, lines[1:]):
        n_seg = max(1, round((b - a) / (units.ZAN_DANG_DOUKOU * d)))
        out += [a + (b - a) * k / n_seg for k in range(1, n_seg)]
        out.append(b)
    return out


def _bracket_set(along_x: bool, pos: float, line: float, z0: float, tiao: int, d: float) -> mesh_mod.Mesh:
    """一攒斗拱：坐斗 → 各跳（顺身向横栱 + 出跳向翘/昂）→ 撑头木 + 内外厢栱。

    ``along_x``：所在檐面沿 X（前后檐）或沿 Y（两山）；``pos`` 为沿檐面坐标，``line`` 为檐柱中线。
    """
    h = LEVEL_HEIGHT_DOUKOU * d

    def blk(len_along: float, len_out: float, za: float, off_out: float = 0.0) -> mesh_mod.Mesh:
        # len_along：顺檐面长；len_out：出跳向长；off_out：出跳向中心偏移
        if along_x:
            return mesh_mod.box(len_along, len_out, za, za + h, cx=pos, cy=line + off_out)
        return mesh_mod.box(len_out, len_along, za, za + h, cx=line + off_out, cy=pos)

    out = blk(SEAT_DOUKOU * d, SEAT_DOUKOU * d, z0)                       # 坐斗
    reach = 0.0
    for j in range(1, tiao + 2):                                          # 各跳 + 撑头木层
        z = z0 + j * h
        reach = min(j, tiao) * units.TIAO_DOUKOU * d                      # 本层出跳（撑头木与末跳齐）
        out = out.merged(blk(ARM_WIDTH_DOUKOU * d, 2.0 * reach + SEAT_DOUKOU * d, z))
        if j <= tiao or tiao == 0:
            out = out.merged(blk(GUA_GONG_DOUKOU * d, ARM_WIDTH_DOUKOU * d, z))   # 正心横栱
    if tiao > 0:                                                           # 里外拽厢栱
        z = z0 + (tiao + 1) * h
        for side in (-1.0, 1.0):
            out = out.merged(blk(XIANG_GONG_DOUKOU * d, ARM_WIDTH_DOUKOU * d, z, side * reach))
    return out


def build_brackets(plan: PlanGeom, column_top_cm: float, tiao: int) -> mesh_mod.Mesh:
    """生成斗拱层网格：自檐柱顶 ``column_top_cm`` 起，高 ``layer_height_cm``。"""
    if tiao < 0:
        raise ValueError(f"出跳数须 ≥0，收到 {tiao}")
    d = plan.doukou_cm
    hl, hw = plan.length / 2.0, plan.width / 2.0
    plate_h, plate_w = PLATE_HEIGHT_DOUKOU * d, PLATE_WIDTH_DOUKOU * d
    z_plate = column_top_cm + plate_h

    # 平板枋：沿檐柱中线一圈（前后檐通长，两山夹于其间）
    out = mesh_mod.Mesh()
    for sy in (-1.0, 1.0):
        out = out.merged(mesh_mod.box(2 * hl + plate_w, plate_w, column_top_cm, z_plate, cy=sy * hw))
    for sx in (-1.0, 1.0):
        out = out.merged(mesh_mod.box(plate_w, 2 * hw - plate_w, column_top_cm, z_plate, cx=sx * hl))

    # 各攒：前后檐沿 X、两山沿 Y；外侧（−Y / +Y / −X / +X）方向由中线正负决定，里外拽对称
    for sy in (-1.0, 1.0):
        for x in _set_positions(plan.x_lines, d):
            out = out.merged(_bracket_set(True, x, sy * hw, z_plate, tiao, d))
    for sx in (-1.0, 1.0):
        for y in _set_positions(plan.y_lines, d)[1:-1]:                    # 角科已由前后檐生成
            out = out.merged(_bracket_set(False, y, sx * hl, z_plate, tiao, d))
        # 角科：两山向再叠一攒（两向柱头科叠合近似）
        for sy in (-1.0, 1.0):
            out = out.merged(_bracket_set(False, sy * hw, sx * hl, z_plate, tiao, d))

    # 挑檐枋：外拽末端一圈（有出跳时），顶与斗拱层顶齐
    if tiao > 0:
        p = projection_cm(d, tiao)
        top = column_top_cm + layer_height_cm(d, tiao)
        fw = FANG_WIDTH_DOUKOU * d
        z0 = top - LEVEL_HEIGHT_DOUKOU * d
        for sy in (-1.0, 1.0):
            out = out.merged(mesh_mod.box(2 * (hl + p) + fw, fw, z0, top, cy=sy * (hw + p)))
        for sx in (-1.0, 1.0):
            out = out.merged(mesh_mod.box(fw, 2 * (hw + p) - fw, z0, top, cx=sx * (hl + p)))
    return out
