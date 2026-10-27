"""plan.py — 柱网平面几何（纯数据推导）。

由斗口、面阔间数、进深间数、平身科数推出各间面宽、柱位与总尺寸。
不依赖 bpy，可直接单测。

出处与推测项：
- 明间面阔 = 攒档 × 平身科数 + 1 斗口：项目约定公式，见 speculative S-009（待核）。
- 次间面阔 = 攒档 × （平身科数 − 1） + 1 斗口：同上简化规则。
- 进深各间等宽 = 攒档 × 进深平身科数 + 1 斗口：speculative S-010。
- 上檐出 21 斗口：units.UPPER_EAVE_PROJECTION_DOUKOU。

小式（无斗拱，grade = 小式）：面阔/进深直接以营造尺给定；柱高 = 明间 × 0.8、
柱径 = 柱高 / 11、上檐出 = 柱高 × 0.3、金柱径 = 檐柱径 + 1 寸（units.XIAOSHI_*，S-039）。
"""

from __future__ import annotations

from dataclasses import dataclass

from generator import units


@dataclass(frozen=True)
class PlanGeom:
    """柱网平面几何（长度单位 cm；原点为柱网几何中心）。

    - X = 面阔方向（长边），Y = 进深方向，正面朝 −Y（ADR-0001）。
    - ``bay_widths`` / ``depth_widths`` 从 −X / −Y 侧向 + 侧排列，明间居中。
    - ``doukou_cm``：大式为斗口；小式为等效模数（檐柱径 / 6，S-039），仅供细部比例。
    """

    doukou_cm: float
    bay_widths: tuple[float, ...]
    depth_widths: tuple[float, ...]
    upper_eave_cm: float
    n_bays: int
    n_depth_bays: int
    column_height_cm: float          # 檐柱高（单层，不含柱础以外的构件）
    eave_column_diameter_cm: float   # 檐柱径
    gold_column_diameter_cm: float   # 金柱径

    @property
    def length(self) -> float:
        """面阔总长（柱中—中）。"""
        return sum(self.bay_widths)

    @property
    def width(self) -> float:
        """进深总宽（柱中—中）。"""
        return sum(self.depth_widths)

    @property
    def eave_length(self) -> float:
        """檐口平面长 = 面阔 + 两侧上檐出。"""
        return self.length + 2.0 * self.upper_eave_cm

    @property
    def eave_width(self) -> float:
        """檐口平面宽 = 进深 + 两侧上檐出。"""
        return self.width + 2.0 * self.upper_eave_cm

    @property
    def x_lines(self) -> list[float]:
        """面阔分位线（含两山），共 n_bays + 1 条。"""
        out: list[float] = []
        x = -self.length / 2.0
        for w in self.bay_widths:
            out.append(x)
            x += w
        out.append(self.length / 2.0)
        return out

    @property
    def y_lines(self) -> list[float]:
        """进深分位线（含前后檐），共 n_depth_bays + 1 条。"""
        out: list[float] = []
        y = -self.width / 2.0
        for w in self.depth_widths:
            out.append(y)
            y += w
        out.append(self.width / 2.0)
        return out


def ming_bay_width(brackets: int, doukou_cm: float) -> float:
    """明间面阔 = 攒档 × 平身科数 + 1 斗口（cm）。"""
    return (units.ZAN_DANG_DOUKOU * brackets + 1.0) * doukou_cm


def side_bay_width(brackets: int, doukou_cm: float) -> float:
    """次间（梢间）面阔 = 攒档 × （平身科数 − 1） + 1 斗口（cm）。"""
    return (units.ZAN_DANG_DOUKOU * (brackets - 1) + 1.0) * doukou_cm


def depth_bay_width(brackets: int, doukou_cm: float) -> float:
    """进深每间面阔 = 攒档 × 平身科数 + 1 斗口（cm，简化，S-010）。"""
    return (units.ZAN_DANG_DOUKOU * brackets + 1.0) * doukou_cm


def build_plan(p) -> PlanGeom:
    """由建筑参数（config.BuildingParams）推平面几何。

    参数 ``p`` 需具备 ``validate()``、``doukou_cm``、``bays``、``depth_bays``、
    ``bay_brackets``、``depth_brackets`` 属性。
    """
    p.validate()
    if getattr(p, "grade", "大式") == "小式":
        return _build_plan_xiaoshi(p)
    d = p.doukou_cm
    ming = ming_bay_width(p.bay_brackets, d)
    side = side_bay_width(p.bay_brackets, d)
    half = (p.bays - 1) // 2
    bays = tuple([side] * half + [ming] + [side] * half)
    dw = depth_bay_width(p.depth_brackets, d)
    depths = tuple([dw] * p.depth_bays)
    return PlanGeom(
        doukou_cm=d,
        bay_widths=bays,
        depth_widths=depths,
        upper_eave_cm=units.UPPER_EAVE_PROJECTION_DOUKOU * d,
        n_bays=p.bays,
        n_depth_bays=p.depth_bays,
        column_height_cm=units.EAVE_COLUMN_HEIGHT_DOUKOU * d,
        eave_column_diameter_cm=units.EAVE_COLUMN_DIAMETER_DOUKOU * d,
        gold_column_diameter_cm=units.GOLD_COLUMN_DIAMETER_DOUKOU * d,
    )


def _build_plan_xiaoshi(p) -> PlanGeom:
    """小式平面：明间 / 次间 / 进深以营造尺给定，柱高柱径按明间面宽推（S-039）。

    次间（含梢间）一律取 ``side_bay_chi``，缺省为明间 × 0.8；
    令 ``side_bay_chi = ming_bay_chi = depth_bay_chi`` 即得各间等宽的方亭。
    """
    ming = units.chi_to_cm(p.ming_bay_chi)
    side = (
        units.chi_to_cm(p.side_bay_chi) if p.side_bay_chi is not None
        else ming * units.XIAOSHI_SIDE_BAY_PER_MING
    )
    half = (p.bays - 1) // 2
    bays = tuple([side] * half + [ming] + [side] * half)
    depths = tuple([units.chi_to_cm(p.depth_bay_chi)] * p.depth_bays)
    col_h = ming * units.XIAOSHI_COLUMN_HEIGHT_PER_MING
    col_d = col_h * units.XIAOSHI_COLUMN_DIAMETER_PER_HEIGHT
    return PlanGeom(
        doukou_cm=col_d * units.XIAOSHI_MODULE_PER_DIAMETER,
        bay_widths=bays,
        depth_widths=depths,
        upper_eave_cm=col_h * units.XIAOSHI_UPPER_EAVE_PER_HEIGHT,
        n_bays=p.bays,
        n_depth_bays=p.depth_bays,
        column_height_cm=col_h,
        eave_column_diameter_cm=col_d,
        gold_column_diameter_cm=col_d + units.cun_to_cm(units.XIAOSHI_GOLD_COLUMN_EXTRA_CUN),
    )


def eave_columns(plan: PlanGeom) -> list[tuple[float, float]]:
    """檐柱柱位（柱中坐标）：前后檐全部分位线 + 两山内分位线（角柱不重复）。"""
    xs = plan.x_lines
    ys = plan.y_lines
    pts: list[tuple[float, float]] = []
    for x in xs:
        pts.append((x, -plan.width / 2.0))
        pts.append((x, plan.width / 2.0))
    for y in ys[1:-1]:
        pts.append((-plan.length / 2.0, y))
        pts.append((plan.length / 2.0, y))
    return pts


def gold_columns(plan: PlanGeom) -> list[tuple[float, float]]:
    """金柱柱位（柱中坐标）：进深内部分位线 × 面阔内部分位线。

    进深 2 间时内分位线只有一条（Y=0），即中柱式一排。
    """
    xs_in = plan.x_lines[1:-1]
    ys_in = plan.y_lines[1:-1]
    return [(x, y) for y in ys_in for x in xs_in]
