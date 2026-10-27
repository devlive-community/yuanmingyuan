"""columns.py — 柱网：檐柱、金柱、柱础。

比例出处（docs/sources/sources.md）：
- 檐柱高 60 斗口、檐柱径 6 斗口：《清式营造则例》大式通例（归纳值，medium）。
- 金柱径 6.6 斗口：归纳值（speculative S-007，low）。
- 金柱高暂取与檐柱同高：简化（S-007；真实金柱需承托梁架并穿过斗拱层）。
- 柱础（鼓镜）础高 ≈ 0.24 × 柱径、础径 = 1.4 × 柱径：推测值（S-007）。
- 小式柱高柱径由 plan 按明间面宽推出（S-039），本模块只取 PlanGeom 上的值。
"""

from __future__ import annotations

from generator import mesh as mesh_mod
from generator import plan as plan_mod
from generator.plan import PlanGeom

CYLINDER_SEGMENTS = 16  # 圆柱面近似分段数（预览精度，可调）


def eave_column_height_cm(plan: PlanGeom) -> float:
    """檐柱高（cm）：大式 60 斗口（不含斗拱层）；小式明间面宽 × 0.8。"""
    return plan.column_height_cm


def build_columns(plan: PlanGeom, platform_top_cm: float, stories: int = 1) -> mesh_mod.Mesh:
    """生成柱网网格：檐柱 + 金柱 + 柱础，合并为单一 Mesh。

    ``platform_top_cm`` 为台基顶标高（柱础坐于台基顶面之上）。
    ``stories=2`` 时柱身通高到二层（楼），柱高 × 2。
    """
    col_h = eave_column_height_cm(plan) * max(1, int(stories))
    eave_r = plan.eave_column_diameter_cm / 2.0
    gold_r = plan.gold_column_diameter_cm / 2.0

    out = mesh_mod.Mesh()
    for (x, y), r in (
        *(((x, y), eave_r) for (x, y) in plan_mod.eave_columns(plan)),
        *(((x, y), gold_r) for (x, y) in plan_mod.gold_columns(plan)),
    ):
        # 柱础（鼓镜）：坐于台基顶
        base_h = 0.24 * (2.0 * r)   # 础高 ≈ 0.24 柱径（S-007 推测）
        base_r = 0.7 * (2.0 * r)    # 础径 = 1.4 柱径（S-007 推测）
        out = out.merged(
            mesh_mod.cylinder(platform_top_cm, platform_top_cm + base_h, base_r, x, y, CYLINDER_SEGMENTS)
        )
        # 柱身：础顶 → 台基顶 + 柱高（金柱暂与檐柱等高，S-007）
        out = out.merged(
            mesh_mod.cylinder(platform_top_cm + base_h, platform_top_cm + col_h, r, x, y, CYLINDER_SEGMENTS)
        )
    return out
