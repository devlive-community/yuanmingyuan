"""units.py — 清式营造模数与单位换算。

所有比例常量集中在本模块，几何逻辑一律从此处取值，不得硬编码换算值
（见项目编码规范与 docs/decisions/ADR-0001）。

长度单位：厘米（场景 1 单位 = 1 cm，对齐 UE5）。

主要出处（详见 docs/sources/sources.md）：
- 小式柱高 = 明间面宽 × 0.8、柱径 = 柱高 / 11：《清式营造则例》小式通例（归纳值）。
- 斗口十一等：《工程做法则例》斗科用材定例（一等六寸，每等递减半寸，至十一等一寸）。
- 檐柱高 60 斗口 / 檐柱径 6 斗口：梁思成《清式营造则例》大式柱高柱径通例（归纳值）。
- 攒档 11 斗口：《清式营造则例》斗科攒当。
- 上檐出 21 斗口：《工程做法则例》上檐出定例（归纳值）；带斗拱者另加斗拱出踩。
- 拽架 3 斗口：《清式营造则例》斗拱每出一跳出踩 3 斗口（归纳值）。
- 举架序列：《工程做法则例》举架做法通行序列（檐步五举起，逐步递增）。
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 可配置常量（cm）
# ---------------------------------------------------------------------------

CHI_TO_CM: float = 32.0      # 1 营造尺 ≈ 32 cm（学界折算约 31.96–32，取 32）
CUN_TO_CM: float = 3.2       # 1 寸 = 0.1 营造尺
SCENE_UNIT_CM: float = 1.0   # 场景 1 单位 = 1 cm（ADR-0001）

# 斗口十一等：一等 6.0 寸 → 十一等 1.0 寸，每等递减 0.5 寸（索引 0 = 一等）
DOUKOU_GRADES_CUN: tuple[float, ...] = tuple(round(6.0 - 0.5 * i, 1) for i in range(11))

# ---------------------------------------------------------------------------
# 大式参考比例（单位：斗口 D）
# ---------------------------------------------------------------------------

ZAN_DANG_DOUKOU: float = 11.0                 # 攒档（相邻斗拱坐斗中—中水平距）
EAVE_COLUMN_HEIGHT_DOUKOU: float = 60.0       # 檐柱高
EAVE_COLUMN_DIAMETER_DOUKOU: float = 6.0      # 檐柱径
GOLD_COLUMN_DIAMETER_DOUKOU: float = 6.6      # 金柱径（归纳值，待核；speculative S-007）
UPPER_EAVE_PROJECTION_DOUKOU: float = 21.0    # 上檐出（檐檩中—檐柱中水平距；有斗拱时自挑檐桁中起算，另加出踩）
TIAO_DOUKOU: float = 3.0                      # 每一拽架（斗拱每出一跳的水平出踩），3 斗口

# ---------------------------------------------------------------------------
# 小式参考比例（无斗拱；以明间面宽 / 檐柱高为基准）
# ---------------------------------------------------------------------------

XIAOSHI_COLUMN_HEIGHT_PER_MING: float = 0.8    # 檐柱高 = 明间面宽 × 8/10（《清式营造则例》小式通例，medium）
XIAOSHI_COLUMN_DIAMETER_PER_HEIGHT: float = 1.0 / 11.0  # 檐柱径 = 柱高 / 11（同上，medium）
XIAOSHI_UPPER_EAVE_PER_HEIGHT: float = 0.3     # 上檐出 = 檐柱高 × 3/10（通行归纳，待核原文；S-039）
XIAOSHI_GOLD_COLUMN_EXTRA_CUN: float = 1.0     # 金柱径 = 檐柱径 + 1 寸（通行归纳，待核；S-039）
XIAOSHI_SIDE_BAY_PER_MING: float = 0.8         # 次间面宽缺省 = 明间 × 8/10（工作假设，可由 side_bay_chi 覆盖；S-039）
XIAOSHI_MODULE_PER_DIAMETER: float = 1.0 / 6.0  # 小式等效模数 = 檐柱径 / 6（仅供脊、宝顶等细部比例借用大式「柱径 6 斗口」，S-039）

# 举架：步数 → 自檐步（檐口侧）至脊步（脊侧）的举值序列（升高 / 水平深）。
# 「檐步五举，逐步递增」为通行序列；步架水平深均分为本步简化（speculative S-003）。
JUAJI_BY_STEPS: dict[int, tuple[float, ...]] = {
    2: (0.50, 0.90),               # 檐步五举、脊步九举
    3: (0.50, 0.75, 0.90),         # 檐步、金步七五举、脊步
    4: (0.50, 0.65, 0.75, 0.90),   # 檐步、下金步六五举、上金步七五举、脊步
}

DEFAULT_ROOF_STEPS: int = 4  # 默认步架数（进深 3 间：檐步 + 两金步 + 脊步）


def doukou_cun(grade: int) -> float:
    """按等第取斗口值（寸）。grade: 1 = 一等（6 寸）… 11 = 十一等（1 寸）。

    出处：《工程做法则例》斗科用材十一等。
    """
    if not 1 <= grade <= 11:
        raise ValueError(f"斗口等第须在 1–11 之间，收到 {grade}")
    return DOUKOU_GRADES_CUN[grade - 1]


def doukou_cm(grade: int) -> float:
    """按等第取斗口值（cm）。"""
    return doukou_cun(grade) * CUN_TO_CM


def cun_to_cm(cun: float) -> float:
    """寸 → cm。"""
    return cun * CUN_TO_CM


def chi_to_cm(chi: float) -> float:
    """营造尺 → cm。"""
    return chi * CHI_TO_CM


def juaji_profile(
    half_span_doukou: float, n_steps: int = DEFAULT_ROOF_STEPS
) -> list[tuple[float, float]]:
    """由举架计算屋面折线剖面（斗口单位）。

    从檐口 ``(0, 0)`` 到屋脊 ``(half_span_doukou, H)``，各步水平深均分
    （speculative S-003），举值取 ``JUAJI_BY_STEPS[n_steps]``，自檐步向脊步递增。

    返回点列 ``[(x0, y0) = 檐口, …, (xn, yn) = 脊]``，共 ``n_steps + 1`` 点。
    """
    if n_steps not in JUAJI_BY_STEPS:
        raise ValueError(f"暂只支持 {sorted(JUAJI_BY_STEPS)} 步举架，收到 {n_steps}")
    jus = JUAJI_BY_STEPS[n_steps]
    step = half_span_doukou / n_steps
    pts: list[tuple[float, float]] = [(0.0, 0.0)]
    x = 0.0
    y = 0.0
    for ju in jus:
        x += step
        y += step * ju
        pts.append((x, y))
    return pts

# ---------------------------------------------------------------------------
# 墙体与装修（小木作）比例（以檐柱径 d / 檐柱高 h 计；见 carpentry.py 与 speculative S-042）
# ---------------------------------------------------------------------------

BEAM_HEIGHT_PER_DIAMETER: float = 1.0          # 檐枋（额枋）高 = 柱径（小式檐枋通例；大式大额枋 6.6 斗口，此处统一简化，S-042）
BEAM_THICK_PER_DIAMETER: float = 0.8           # 檐枋厚 = 0.8 柱径（小式通例，medium）
SILL_WALL_PER_COLUMN_HEIGHT: float = 0.3       # 槛墙高 = 檐柱高 × 3/10（《清式营造则例》通例，medium）
WALL_BASE_PER_COLUMN_HEIGHT: float = 0.3       # 山墙/后檐墙下碱高 = 檐柱高 × 3/10（通例，medium）
WALL_THICK_PER_DIAMETER: float = 1.5           # 墙上身厚 = 1.5 柱径，柱子包在墙内（简化，S-042）
WALL_BASE_PROUD_CM: float = 3.0                # 下碱比上身每侧宽出（花碱，工作假设，S-042）
LOWER_SILL_PER_DIAMETER: float = 0.8           # 下槛高 = 0.8 柱径（通行归纳，待核，S-042）
RAIL_PER_DIAMETER: float = 0.6                 # 中槛 / 上槛高、抱框宽 = 0.6 柱径（通行归纳，待核，S-042）
TRANSOM_PER_OPENING: float = 0.16              # 横披（中槛—上槛）占门窗口净高的比例（工作假设，S-042）
LATTICE_SHARE: float = 0.6                     # 槅扇：槅心占扇高 6/10、裙板与绦环 4/10（「六四分」通例，medium）
