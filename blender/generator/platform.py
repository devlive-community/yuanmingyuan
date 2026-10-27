"""platform.py — 台基：台明（长方体）＋可选月台与踏跺。

台明外扩取上檐出（S-001 简化）。

正大光明殿的月台与「南出三路九级垂带踏跺」为史料记载（圆明园管理处论文 2011，
medium，见 docs/sources/research-zhengda-guangming.md 参数 4）；
月台进深/面阔、踏跺水平深、垂带宽为工作假设（speculative S-015）。
"""

from __future__ import annotations

from generator import mesh as mesh_mod
from generator.plan import PlanGeom

STAGE_DEPTH_CM: float = 300.0    # 月台进深（工作假设，S-015）
STAIR_TREAD_CM: float = 30.0     # 踏跺每级水平深（工作假设，S-015）
DAITING_WIDTH_CM: float = 32.0   # 垂带宽（1 营造尺，工作假设，S-015）
FLIGHT_GAP_CM: float = 32.0      # 各路踏跺之间的间隔（工作假设，S-015）


def platform_plan_size(plan: PlanGeom) -> tuple[float, float]:
    """台基平面尺寸（cm）：柱中外扩一个上檐出（S-001 简化）。"""
    return plan.eave_length, plan.eave_width


def build_platform(plan: PlanGeom, height_cm: float, params=None) -> mesh_mod.Mesh:
    """生成台基网格。z 从 0（地坪）到 ``height_cm``（台基顶）。

    ``params`` 为 config.BuildingParams（或同名字段对象）时，
    依据 ``moon_platform / stairs_flights / stairs_steps`` 追加月台与踏跺。
    """
    if height_cm <= 0:
        raise ValueError(f"台基高度须为正，收到 {height_cm}")
    sx, sy = platform_plan_size(plan)
    out = mesh_mod.box(sx, sy, 0.0, height_cm)

    if params is not None and getattr(params, "moon_platform", False):
        flights = int(getattr(params, "stairs_flights", 3))
        steps = int(getattr(params, "stairs_steps", 9))
        stage_w = _moon_stage_width(plan)
        out = out.merged(_moon_stage_platform(plan, height_cm, stage_w))
        out = out.merged(_stairs(plan, height_cm, stage_w, flights, steps))
    return out


def _moon_stage_width(plan: PlanGeom) -> float:
    """月台面阔：取殿身中部三间面阔之和（工作假设，S-015）。"""
    n = plan.n_bays
    if n >= 5:
        idx = (n - 3) // 2
        return sum(plan.bay_widths[idx: idx + 3])
    return sum(plan.bay_widths)


def _moon_stage_platform(plan: PlanGeom, height_cm: float, stage_w: float) -> mesh_mod.Mesh:
    """月台：贴于台明前檐（−Y）的长方体，与台明同高。"""
    front_y = -plan.eave_width / 2.0
    cy = front_y - STAGE_DEPTH_CM / 2.0
    return mesh_mod.box(stage_w, STAGE_DEPTH_CM, 0.0, height_cm, cy=cy)


def _stairs(plan: PlanGeom, height_cm: float, stage_w: float, flights: int, steps: int) -> mesh_mod.Mesh:
    """三路踏跺＋垂带：各级为实心台阶盒体，垂带为楔形体（简化，S-015）。

    第一级顶面与月台面同高，逐级下降 ``height_cm / steps``。
    """
    if flights < 1 or steps < 1:
        raise ValueError("踏跺路数与级数须 ≥1")
    flight_w = (stage_w - (flights - 1) * FLIGHT_GAP_CM) / flights
    if flight_w <= 0:
        raise ValueError("踏跺路数过多：单路宽度 ≤ 0")
    rise = height_cm / steps
    front_y = -plan.eave_width / 2.0 - STAGE_DEPTH_CM

    out = mesh_mod.Mesh()
    for i in range(flights):
        cx = (i - (flights - 1) / 2.0) * (flight_w + FLIGHT_GAP_CM)
        for k in range(steps):
            top = height_cm - k * rise
            cy = front_y - (k + 0.5) * STAIR_TREAD_CM
            out = out.merged(
                mesh_mod.box(flight_w, STAIR_TREAD_CM, 0.0, top, cx=cx, cy=cy)
            )
        # 垂带：两侧楔形体，顶面自月台面（后）降至最下一级顶面（前）
        for side in (-1.0, 1.0):
            xw = cx + side * (flight_w / 2.0 + DAITING_WIDTH_CM / 2.0)
            out = out.merged(
                mesh_mod.wedge(
                    DAITING_WIDTH_CM,
                    steps * STAIR_TREAD_CM,
                    0.0,
                    height_cm,
                    rise,
                    cx=xw,
                    cy=front_y - steps * STAIR_TREAD_CM / 2.0,
                )
            )
    return out
