"""western.py — 西洋楼建筑家族（v3：海晏堂按铜版画四面 + 样式雷图说 + 考古 + OSM 重建）。

西洋楼为欧洲巴洛克手法与中国工匠做法结合，**不走斗口/举架尺寸体系**，
本模块用直接尺寸（cm）＋模块级常量表；每项常量的依据见注释中的编号，
对应 docs/sources/research-haiyantang.md（v3），推测项见 docs/speculative.md S-023。

海晏堂构成（research §一–§四）：
- 正楼（西楼）**坐东面西**，上下各十一间（2+2+3+2+2）：两端方亭式翼楼、中三间门罩，
  孔雀绿琉璃瓦庑殿顶，墙身粉红色灰、汉白玉石柱；南北下层为平台小屋。
- 楼前左右叠落石跑梯自二层门前平台下行、再折向西落地，环抱「菱形」喷水池；
  池后八字两墙列十二生肖像（南：鼠虎龙马猴狗；北：牛兔蛇羊鸡猪，由内向外），
  后中石蚌、池中喷水塔；梯脚外八角石鼎一对；导水台两侧共六十。
- 楼后「工」字蓄水楼：南北面各十三间（3+7+3，三门十窗），檐上女儿墙，
  楼顶中段锡海（27.36 × 5.72 × 1.44 m），两端方亭式水车房；东端阶台四折石梯；
  楼南北八角喷水池各二、中央圆形喷泉。

局部坐标：+X 东、+Y 北，原点 = 蓄水楼中心（对齐 OSM 蓄水楼 POI）；z = 地坪 0。
网格标签：英文 id，末段为材质类（walls / marble / glazed_roof / windows / water / …），
中文名只在页面渲染时查表（web/app/src/labels.ts）。
"""

from __future__ import annotations

import math
from pathlib import Path

from generator import mesh as mesh_mod
from generator import sculpt
from generator import terrain as terrain_mod

Part = tuple[str, mesh_mod.Mesh]

# ---------------------------------------------------------------------------
# 尺寸常量（cm）。依据编号见 research-haiyantang.md；除注明 medium 外均为 low（S-023）
# ---------------------------------------------------------------------------

# 工字蓄水楼（§四、§五）
RES_LEN_CM = 5560.0            # 东西通长：OSM 遗址轮廓 55.6 m（A2），与铜版画+锡海推算 59 m 互证
RES_END_LEN_CM = 1330.0        # 两端段东西长（铜版画南面 3:7:3 段比）
RES_MID_LEN_CM = RES_LEN_CM - 2 * RES_END_LEN_CM   # 中段 29.0 m（容锡海 27.36 m）
RES_END_DEPTH_CM = 2500.0      # 两端段南北进深：OSM 25 m
RES_MID_DEPTH_CM = 2200.0      # 中段南北进深（读图：两端段微凸）
RES_EAVE_CM = 1310.0           # 檐高（南面图上比例）
RES_PARAPET_CM = 160.0         # 檐上花饰女儿墙高
RES_END_BAYS, RES_MID_BAYS = 3, 7   # 南北面各十三间（考古通报，high；铜版画互证）

TIN_SEA_LEN_CM = 2736.0        # 锡海东西长 27.36 m（澎湃，medium；维基八丈五尺五寸吻合）
TIN_SEA_WID_CM = 572.0         # 南北宽 5.72 m（澎湃；维基一丈八尺五寸≈5.92 m，取米制）
TIN_SEA_DEPTH_CM = 144.0       # 深 1.44 m
TIN_RIM_CM = 30.0              # 锡板池壁厚（工作假设）

WHEEL_LEN_CM = 950.0           # 水车房东西长（南面图比例）
WHEEL_WID_CM = 1000.0          # 水车房南北宽（工作假设）
WHEEL_WALL_CM = 600.0          # 水车房墙高
WHEEL_ROOF_RISE_CM = 300.0     # 方亭式屋顶升起

# 东端阶台与四折石梯（铜版画东面）：三级台，(东凸深, 半宽, 台顶高)
EAST_TIERS = ((1000.0, 1250.0, 440.0), (650.0, 950.0, 880.0), (330.0, 650.0, RES_EAVE_CM))
EAST_FLIGHT_DEPTH_CM = 330.0   # 每跑梯段宽（东西向）
EAST_STEPS_PER_FLIGHT = 24

# 正楼（§二、§五）
REAR_GAP_CM = 900.0            # 正楼与蓄水楼之间：楼后三间殿（样式雷图说）进深（读图）
MAIN_DEPTH_CM = 1050.0         # 正楼进深（「深一间」+ 南面图翼楼侧面）
MAIN_EAST_X = -RES_LEN_CM / 2.0 - REAR_GAP_CM
MAIN_WEST_X = MAIN_EAST_X - MAIN_DEPTH_CM
# 自南至北五段面宽：南翼楼 2 间、券窗 2 间、中三间、券窗 2 间、北翼楼 2 间（铜版画西面段比）
MAIN_SEGMENTS_CM = (1092.0, 629.0, 1758.0, 629.0, 1092.0)
MAIN_SEGMENT_BAYS = (2, 2, 3, 2, 2)                     # 共十一间（medium）
MAIN_LEN_CM = sum(MAIN_SEGMENTS_CM)                     # 52 m
PAVILION_PROJ_CM = 150.0       # 翼楼前凸
FRONT_PROJ_CM = 100.0          # 中三间门罩前凸
FLOOR2_CM = 830.0              # 二层地面（西面图：二层门槛 ≈ 檐高 57%）
MAIN_EAVE_CM = 1460.0          # 檐高
MAIN_ROOF_RISE_CM = 380.0      # 主庑殿顶升起
PAVILION_ROOF_RISE_CM = 450.0  # 翼楼方亭式顶升起（铜版画：高出主脊）
ROOF_OVERHANG_CM = 60.0
CREST_TOP_CM = 2050.0          # 中三间门罩山花顶（琉璃番花葫芦顶）
WING_LEN_CM = 700.0            # 南北下层平台小屋（样式雷图说）面宽（工作假设）
RAIL_H_CM = 100.0              # 石栏杆高
PLINTH_H_CM = 70.0             # 勒脚高（工作假设）
CORNICE_H_CM = 45.0            # 檐口线脚高（工作假设）
PILASTER_W_CM, PILASTER_D_CM = 55.0, 25.0   # 壁柱宽、凸出（铜版画逐间壁柱，尺寸工作假设）
SKIN_CM = 35.0                 # 立面墙皮厚：门窗洞口在其中开出，玻璃退进墙皮内（工作假设）
BALUSTER_STEP_CM = 26.0        # 栏杆柱间距（工作假设）
ARCH_SEGMENTS = 12
RAIL_T_CM = 20.0

# 楼前石梯与水池（§三）
LANDING_DEPTH_CM = 400.0       # 二层门前平台（东西）
LANDING_HALF_CM = 600.0        # 平台半宽（南北）
STAIR_W_CM = 350.0             # 梯宽
UPPER_RUN_END_CM = 1700.0      # 上跑（沿楼南北下行）止于 |y|
MID_LANDING_CM = 400.0         # 转折平台南北长
MID_LANDING_Z_CM = 450.0       # 转折平台高
LOWER_RUN_CM = 2000.0          # 下跑（折向西）水平长
UPPER_STEPS, LOWER_STEPS = 25, 30   # 共约五十五级（「数十级」）；下跑每侧 30 导水台，两侧共 60（维基，medium）
CASCADE_W_CM = 60.0

POOL_BACK_X = -5300.0          # 池后缘（石蚌）
POOL_BACK_HALF_CM = 450.0
POOL_SHOULDER_X = -6500.0      # 八字墙西端
POOL_HALF_CM = 1450.0          # 池半宽（南北；留出生肖石台与导水台的位置）
POOL_FRONT_X = -7400.0         # 前缘外凸顶点
POOL_WALL_T_CM = 40.0
POOL_CURB_CM = 45.0            # 池沿高出地坪
POOL_FLOOR_CM = -80.0
POOL_WATER_CM = 10.0           # 池水面（略高于地坪，低于池沿）
POOL_ARC_SEGMENTS = 16

ZODIAC_SOUTH = ("rat", "tiger", "dragon", "horse", "monkey", "dog")   # 由内（东）向外（西），medium
ZODIAC_NORTH = ("ox", "rabbit", "snake", "goat", "rooster", "pig")
ZODIAC_OFFSET_CM = 110.0       # 石台中心距八字墙中线外移（墙半厚 + 台半宽 + 间隙）
PLINTH_CM, PLINTH_H_CM = 90.0, 120.0
FIGURE_W_CM, FIGURE_H_CM, HEAD_CM = 55.0, 90.0, 32.0  # 人身兽首坐像（工作假设）
SEATED_ASSET_DIR = Path(__file__).resolve().parents[2] / "assets" / "zodiac_seated"  # 盘坐身躯模型（见 docs/sources/zodiac-heads-assets.md）
SEATED_HEIGHT_CM = 140.0       # 盘坐像连原头通高（工作假设：与人坐高相当）
SEATED_NECK = 0.72             # 颈部所在高度（占通高），以上换装生肖铜首
HEAD_SCALE = 1.4               # 兽首（含颈）约 45 cm 高：现存铜首「高约 50 厘米」（城大展，medium）

SHELL_X, SHELL_R_CM, SHELL_H_CM = -5400.0, 110.0, 200.0   # 石蚌约高 2 m（城大展，medium）
FOUNTAIN_X = -6550.0
URN_POS = (-7500.0, 2350.0)
URN_PEDESTAL_R_CM, URN_PEDESTAL_H_CM = 110.0, 180.0
URN_R_CM, URN_H_CM = 75.0, 260.0   # 八角石鼎高八尺余≈2.6 m（维基，medium）

COURT_WEST_X = -9500.0         # 楼前广场西缘（OSM 西段轮廓，粗略）
COURT_HALF_CM = 3300.0

# 楼南北喷水池（§四 4.8–4.9）
GARDEN_FOUNTAIN_Y = RES_END_DEPTH_CM / 2.0 + 900.0
OCTAGON_R_CM, ROUND_R_CM = 280.0, 300.0
FOUNTAIN_CURB_CM = 60.0


# ---------------------------------------------------------------------------
# 基础形体
# ---------------------------------------------------------------------------

def hip_roof(length: float, width: float, rise: float, z0: float = 0.0,
             cx: float = 0.0, cy: float = 0.0) -> mesh_mod.Mesh:
    """直坡庑殿顶（西洋楼式直坡，非中式举架曲线）：长边沿 X，两梯形坡＋两三角披。"""
    hl, hw = length / 2.0, width / 2.0
    rl = max(length - width, 0.0) / 2.0  # 正脊半长
    v = [
        (cx - hl, cy - hw, z0), (cx + hl, cy - hw, z0),
        (cx + hl, cy + hw, z0), (cx - hl, cy + hw, z0),
        (cx - rl, cy, z0 + rise), (cx + rl, cy, z0 + rise),
    ]
    f = [
        (0, 1, 5, 4),  # 南坡（−Y）
        (3, 2, 5, 4),  # 北坡（+Y）
        (1, 2, 5),     # 东披（三角）
        (3, 0, 4),     # 西披（三角）
    ]
    return mesh_mod.Mesh(vertices=[tuple(p) for p in v], faces=[tuple(x) for x in f])


def hip_roof_xy(cx: float, cy: float, len_x: float, len_y: float, z0: float, rise: float) -> mesh_mod.Mesh:
    """任意朝向的直坡庑殿顶：自动以长边为脊向（正方形时略加 1 cm 免退化）。"""
    if abs(len_x - len_y) < 1.0:
        len_x += 1.0
    if len_x >= len_y:
        return hip_roof(len_x, len_y, rise, z0, cx, cy)
    return hip_roof(len_y, len_x, rise, z0).rotated_z(90.0).translated(dx=cx, dy=cy)


def beam(p0: tuple[float, float, float], p1: tuple[float, float, float], width: float) -> mesh_mod.Mesh:
    """沿任意三维线段的方截面梁（屋脊、垂脊用）。"""
    d = [b - a for a, b in zip(p0, p1)]
    length = math.sqrt(sum(c * c for c in d))
    d = [c / length for c in d]
    ref = (0.0, 0.0, 1.0) if abs(d[2]) < 0.9 else (1.0, 0.0, 0.0)
    u = (d[1] * ref[2] - d[2] * ref[1], d[2] * ref[0] - d[0] * ref[2], d[0] * ref[1] - d[1] * ref[0])
    un = math.sqrt(sum(c * c for c in u))
    u = [c / un * width / 2.0 for c in u]
    v = (d[1] * u[2] - d[2] * u[1], d[2] * u[0] - d[0] * u[2], d[0] * u[1] - d[1] * u[0])
    corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    verts = []
    for p in (p0, p1):
        for su, sv in corners:
            verts.append(tuple(p[i] + su * u[i] + sv * v[i] for i in range(3)))
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return mesh_mod.Mesh(vertices=verts, faces=faces)


def hip_ridges(cx: float, cy: float, len_x: float, len_y: float, z0: float, rise: float,
               width: float = 35.0) -> mesh_mod.Mesh:
    """直坡庑殿顶的正脊与四条垂脊（与 hip_roof_xy 同几何），略抬高以免与坡面共面。"""
    if abs(len_x - len_y) < 1.0:
        len_x += 1.0
    along_x = len_x >= len_y
    hl, hw = (len_x / 2.0, len_y / 2.0) if along_x else (len_y / 2.0, len_x / 2.0)
    rl = (hl - hw)
    lift = width / 2.0

    def pt(a: float, b: float, z: float) -> tuple[float, float, float]:
        return (cx + a, cy + b, z + lift) if along_x else (cx - b, cy + a, z + lift)

    top = z0 + rise
    out = mesh_mod.Mesh()
    if rl > 1.0:
        out = out.merged(beam(pt(-rl, 0.0, top), pt(rl, 0.0, top), width * 1.3))
    for sa in (-1.0, 1.0):
        for sb in (-1.0, 1.0):
            out = out.merged(beam(pt(sa * hl, sb * hw, z0), pt(sa * rl, 0.0, top), width))
    return out


def extrude_vertical(poly: list[tuple[float, float]], plane: str, a0: float, a1: float) -> mesh_mod.Mesh:
    """竖直面内二维轮廓沿法向挤出（支持凹形，如券口上方的拱肩）。

    ``plane='x'``：轮廓坐标为 (y, z)，沿 X 自 a0 至 a1；``plane='y'``：轮廓为 (x, z)，沿 Y。
    """
    pts = list(poly)
    area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))
    if area < 0:
        pts = pts[::-1]                                  # triangulate 的索引按逆时针输入给出
    tris = terrain_mod.triangulate(pts)
    n = len(pts)

    def v(u: float, z: float, a: float) -> tuple[float, float, float]:
        return (a, u, z) if plane == "x" else (u, a, z)

    verts = [v(u, z, a0) for u, z in pts] + [v(u, z, a1) for u, z in pts]
    faces: list[tuple[int, ...]] = []
    for i, j, k in tris:
        faces += [(i, j, k), (n + i, n + k, n + j)]
    for k in range(n):
        k2 = (k + 1) % n
        faces.append((k, k2, n + k2, n + k))
    return mesh_mod.Mesh(vertices=verts, faces=faces)


def _arc(uc: float, zc: float, r: float, t0: float, t1: float, n: int = ARCH_SEGMENTS) -> list[tuple[float, float]]:
    return [(uc + r * math.cos(t0 + (t1 - t0) * k / n), zc + r * math.sin(t0 + (t1 - t0) * k / n))
            for k in range(n + 1)]


def opening_bay(plane: str, face: float, out: float, u0: float, u1: float, z0: float, z1: float,
                ua: float, ub: float, z_sill: float, z_head: float, arch: bool
                ) -> tuple[mesh_mod.Mesh, mesh_mod.Mesh, mesh_mod.Mesh]:
    """一间立面墙皮（含门窗洞口）：返回 (墙皮, 退进的玻璃/门扇, 汉白玉窗台与券口)。

    墙皮自墙面 ``face`` 向外（``out`` = ±1）厚 SKIN_CM；洞口 [ua, ub] × [z_sill, z_head]，
    ``arch`` 时洞口顶为半圆券（券心在 z_head）。
    """
    lo, hi = sorted((face, face + out * SKIN_CM))
    outer = face + out * SKIN_CM

    def rect(a: float, b: float, za: float, zb: float, r0: float = lo, r1: float = hi) -> mesh_mod.Mesh:
        if b - a < 0.5 or zb - za < 0.5:
            return mesh_mod.Mesh()
        return extrude_vertical([(a, za), (b, za), (b, zb), (a, zb)], plane, r0, r1)

    r = (ub - ua) / 2.0
    uc = (ua + ub) / 2.0
    skin = rect(u0, ua, z0, z1).merged(rect(ub, u1, z0, z1)).merged(rect(ua, ub, z0, z_sill))
    if arch:
        top = min(z1, z_head + r + 25.0)
        # 拱肩轮廓：左起拱点 → 沿券弧到右起拱点 → 右上 → 左上
        spandrel = [(ua, z_head)] + _arc(uc, z_head, r, math.pi, 0.0)[1:-1] + [(ub, z_head), (ub, top), (ua, top)]
        skin = skin.merged(extrude_vertical(spandrel, plane, lo, hi)).merged(rect(ua, ub, top, z1))
        glass_outline = [(ua, z_sill), (ub, z_sill), (ub, z_head)] + _arc(uc, z_head, r, 0.0, math.pi)[1:-1] + [(ua, z_head)]
    else:
        skin = skin.merged(rect(ua, ub, z_head, z1))
        glass_outline = [(ua, z_sill), (ub, z_sill), (ub, z_head), (ua, z_head)]
    g0, g1 = sorted((face + out * 2.0, face + out * 8.0))
    glass = extrude_vertical(glass_outline, plane, g0, g1)
    m0, m1 = sorted((outer, outer + out * 12.0))
    marble = rect(ua - 12.0, ub + 12.0, z_sill - 14.0, z_sill, m0, m1)                       # 窗台
    if arch:                                                                                   # 券口（券边石 + 拱心石）
        ring = _arc(uc, z_head, r + 9.0, 0.0, math.pi)
        for (ua_, za_), (ub_, zb_) in zip(ring, ring[1:]):
            pa = (outer + out * 6.0, ua_, za_) if plane == "x" else (ua_, outer + out * 6.0, za_)
            pb = (outer + out * 6.0, ub_, zb_) if plane == "x" else (ub_, outer + out * 6.0, zb_)
            marble = marble.merged(beam(pa, pb, 16.0))
        marble = marble.merged(rect(uc - 14.0, uc + 14.0, z_head + r - 6.0, z_head + r + 30.0, m0, m1))
        h0, h1 = sorted((outer, outer + out * 22.0))                                          # 券上帽檐
        marble = marble.merged(rect(ua - 30.0, ub + 30.0, z_head + r + 30.0, z_head + r + 44.0, h0, h1))
    else:
        marble = marble.merged(rect(ua - 12.0, ub + 12.0, z_head, z_head + 16.0, m0, m1))      # 过梁线
        for e in (ua - 12.0, ub):                                                              # 耳框（两竖边）
            marble = marble.merged(rect(e, e + 12.0, z_sill, z_head, m0, m1))
        for e in (ua - 24.0, ub + 12.0):                                                       # 上角出耳
            marble = marble.merged(rect(e, e + 12.0, z_head - 30.0, z_head + 16.0, m0, m1))
        h0, h1 = sorted((outer, outer + out * 20.0))                                          # 窗上帽檐
        marble = marble.merged(rect(ua - 32.0, ub + 32.0, z_head + 28.0, z_head + 42.0, h0, h1))
    return skin, glass, marble


def lathe(profile: list[tuple[float, float]], cx: float, cy: float, z0: float, seg: int = 10,
          phase_deg: float = 0.0) -> mesh_mod.Mesh:
    """旋转体（瓶、柱础、坐像身）：``profile`` 为自下而上的 (半径, 高) 点列，绕竖轴旋转。"""
    rings = [[(cx + r * math.cos(math.radians(phase_deg) + 2 * math.pi * k / seg),
               cy + r * math.sin(math.radians(phase_deg) + 2 * math.pi * k / seg), z0 + h) for k in range(seg)]
             for r, h in profile]
    verts = [v for ring in rings for v in ring]
    faces: list[tuple[int, ...]] = []
    for i in range(len(rings) - 1):
        for k in range(seg):
            k2 = (k + 1) % seg
            faces.append((i * seg + k, i * seg + k2, (i + 1) * seg + k2, (i + 1) * seg + k))
    faces.append(tuple(range(seg - 1, -1, -1)))                                     # 底
    faces.append(tuple(range((len(rings) - 1) * seg, len(rings) * seg)))            # 顶
    return mesh_mod.Mesh(vertices=verts, faces=faces)


def _scaled(profile: list[tuple[float, float]], rs: float, hs: float) -> list[tuple[float, float]]:
    return [(r * rs, h * hs) for r, h in profile]


# 瓶式栏杆柱（巴洛克常见的单腹瓶形；归一化：半径 cm × 高 0–1）
BALUSTER_PROFILE = [(5.5, 0.0), (5.5, 0.08), (4.0, 0.12), (8.5, 0.35), (7.5, 0.5), (3.6, 0.72),
                    (4.5, 0.82), (5.5, 0.9), (5.5, 1.0)]
# 西洋瓶饰（座、腹、颈、盖、钮）
URN_PROFILE = [(17, 0), (17, 6), (9, 10), (9, 16), (22, 26), (27, 40), (20, 54), (12, 58), (15, 62),
               (6, 68), (8, 74), (0.1, 82)]


def balustrade(xa: float, ya: float, xb: float, yb: float, z: float, h: float = RAIL_H_CM) -> mesh_mod.Mesh:
    """石栏杆：地栿 + 扶手 + 等距瓶式栏杆柱（旋转体）。"""
    out = obox(xa, ya, xb, yb, 22.0, z, z + 12.0).merged(obox(xa, ya, xb, yb, 24.0, z + h - 12.0, z + h))
    n = max(1, int(math.hypot(xb - xa, yb - ya) / BALUSTER_STEP_CM))
    prof = [(r, hh * (h - 24.0)) for r, hh in BALUSTER_PROFILE]
    for k in range(n):
        t = (k + 0.5) / n
        out = out.merged(lathe(prof, xa + (xb - xa) * t, ya + (yb - ya) * t, z + 12.0, seg=6))
    return out


def stepped_balustrade(xa: float, ya: float, xb: float, yb: float, za: float, zb: float, steps: int) -> mesh_mod.Mesh:
    """随踏步升降的阶状石栏杆（每级一段）。"""
    out = mesh_mod.Mesh()
    for k in range(steps):
        t0, t1 = k / steps, (k + 1) / steps
        top = za + (zb - za) * (k + 0.5) / steps
        out = out.merged(balustrade(xa + (xb - xa) * t0, ya + (yb - ya) * t0,
                                    xa + (xb - xa) * t1, ya + (yb - ya) * t1, top))
    return out


def urn(x: float, y: float, z: float, scale: float = 1.0) -> mesh_mod.Mesh:
    """西洋瓶饰（女儿墙、壁柱顶、山花）：旋转体（座、腹、颈、盖、钮）。"""
    return lathe(_scaled(URN_PROFILE, scale, scale), x, y, z, seg=12)


def jet(p0: tuple[float, float, float], p1: tuple[float, float, float]) -> mesh_mod.Mesh:
    """喷水标记（查看器隐藏它，按其两端生成水柱粒子）：p0 喷口；p1 落点（抛物线），
    或 p1 在 p0 正上方时为竖直喷泉、p1 为最高点。标签末段须为 ``jet``。"""
    return beam(p0, p1, 2.0)


def frustum(cx: float, cy: float, z0: float, z1: float, r0: float, r1: float, seg: int = 10) -> mesh_mod.Mesh:
    """竖直锥台（修剪树冠层、线法松层盘）。"""
    verts = [(cx + r * math.cos(2 * math.pi * k / seg), cy + r * math.sin(2 * math.pi * k / seg), z)
             for z, r in ((z0, r0), (z1, r1)) for k in range(seg)]
    verts += [(cx, cy, z0), (cx, cy, z1)]
    faces: list[tuple[int, ...]] = []
    for k in range(seg):
        k2 = (k + 1) % seg
        faces += [(k, k2, seg + k2, seg + k), (2 * seg, k2, k), (2 * seg + 1, seg + k, seg + k2)]
    return mesh_mod.Mesh(vertices=verts, faces=faces)


def topiary(x: float, y: float, tiers: int = 3, height: float = 320.0, radius: float = 110.0
            ) -> tuple[mesh_mod.Mesh, mesh_mod.Mesh]:
    """修剪成层的树（铜版画中的层叠圆锥树 / 线法松）：返回 (树冠, 树干)。"""
    trunk = mesh_mod.cylinder(0.0, height * 0.35, 10.0 + radius * 0.06, x, y, 8)
    crown = mesh_mod.Mesh()
    z = height * 0.25
    tier_h = (height - z) / tiers
    for k in range(tiers):
        r = radius * (1.0 - 0.22 * k)
        crown = crown.merged(frustum(x, y, z, z + tier_h * 0.55, r * 0.55, r))
        crown = crown.merged(frustum(x, y, z + tier_h * 0.55, z + tier_h, r, r * 0.25))
        z += tier_h * 0.8
    return crown, trunk


def obox(x0: float, y0: float, x1: float, y1: float, width: float, z0: float, z1: float) -> mesh_mod.Mesh:
    """沿线段 (x0,y0)→(x1,y1) 的长方体（斜墙、斜石台、栏杆用），宽 ``width``。"""
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    return (mesh_mod.box(length, width, z0, z1)
            .rotated_z(math.degrees(math.atan2(dy, dx)))
            .translated(dx=(x0 + x1) / 2.0, dy=(y0 + y1) / 2.0))


def polygon_ring(points: list[tuple[float, float]], thickness: float, z0: float, z1: float) -> mesh_mod.Mesh:
    """沿闭合多边形各边的墙圈（池壁、女儿墙）。"""
    out = mesh_mod.Mesh()
    for (xa, ya), (xb, yb) in zip(points, points[1:] + points[:1]):
        out = out.merged(obox(xa, ya, xb, yb, thickness, z0, z1))
    return out


def regular_polygon(cx: float, cy: float, r: float, n: int, phase_deg: float = 0.0) -> list[tuple[float, float]]:
    """正 n 边形顶点（逆时针）。八角池 n=8 时取 22.5° 相位使边朝正向。"""
    return [(cx + r * math.cos(math.radians(phase_deg + 360.0 * k / n)),
             cy + r * math.sin(math.radians(phase_deg + 360.0 * k / n))) for k in range(n)]


def flight(xa: float, ya: float, xb: float, yb: float, width: float,
           za: float, zb: float, steps: int, z_base: float = 0.0) -> mesh_mod.Mesh:
    """一跑石阶：自 A（顶面 za）到 B（顶面 zb），``steps`` 级实心踏步，底至 ``z_base``。"""
    out = mesh_mod.Mesh()
    for k in range(steps):
        t0, t1 = k / steps, (k + 1) / steps
        top = za + (zb - za) * (k + 0.5) / steps
        if top - z_base < 1.0:
            continue
        out = out.merged(obox(xa + (xb - xa) * t0, ya + (yb - ya) * t0,
                              xa + (xb - xa) * t1, ya + (yb - ya) * t1, width, z_base, top))
    return out


def _panel_y(y_face: float, xc: float, w: float, z0: float, z1: float, outward: float) -> mesh_mod.Mesh:
    """南北向立面上的门窗暗面板。"""
    return mesh_mod.box(w, 6.0, z0, z1, cx=xc, cy=y_face + outward * 4.0)


# ---------------------------------------------------------------------------
# 海晏堂分部
# ---------------------------------------------------------------------------

def _reservoir_outline() -> list[tuple[float, float]]:
    """工字蓄水楼平面轮廓（逆时针）。"""
    hl, ex = RES_LEN_CM / 2.0, RES_MID_LEN_CM / 2.0
    he, hm = RES_END_DEPTH_CM / 2.0, RES_MID_DEPTH_CM / 2.0
    return [(-hl, -he), (-ex, -he), (-ex, -hm), (ex, -hm), (ex, -he), (hl, -he),
            (hl, he), (ex, he), (ex, hm), (-ex, hm), (-ex, he), (-hl, he)]


def build_reservoir_hall() -> list[Part]:
    """工字蓄水楼：实心楼体、女儿墙、南北面三门十窗、锡海、两端水车房、东端四折石梯。"""
    parts: list[Part] = []
    outline = _reservoir_outline()
    parts.append(("reservoir_hall/walls",
                  terrain_mod.polygon_slab(outline, z_top=RES_EAVE_CM, depth=RES_EAVE_CM)))
    trim = polygon_ring(outline, 2 * (SKIN_CM + 5.0), RES_EAVE_CM, RES_EAVE_CM + RES_PARAPET_CM)   # 花饰女儿墙
    trim = trim.merged(polygon_ring(outline, 2 * (SKIN_CM + 12.0), 0.0, PLINTH_H_CM))              # 勒脚
    trim = trim.merged(polygon_ring(outline, 2 * (SKIN_CM + 25.0), RES_EAVE_CM - CORNICE_H_CM, RES_EAVE_CM))  # 檐口
    parts.append(("reservoir_hall/marble", trim))

    # 南北面各十三间：两端段 3 间、中段 7 间，各段正中为券门，余为方窗，窗上椭圆花饰（铜版画南/北面）
    skin, glass, wtrim = mesh_mod.Mesh(), mesh_mod.Mesh(), mesh_mod.Mesh()
    hl, ex = RES_LEN_CM / 2.0, RES_MID_LEN_CM / 2.0
    segs = ((-hl, -ex, RES_END_BAYS, RES_END_DEPTH_CM), (-ex, ex, RES_MID_BAYS, RES_MID_DEPTH_CM),
            (ex, hl, RES_END_BAYS, RES_END_DEPTH_CM))
    for xa, xb, bays, depth in segs:
        bw = (xb - xa) / bays
        for k in range(bays):
            u0, u1 = xa + bw * k, xa + bw * (k + 1)
            xc = (u0 + u1) / 2.0
            door = k == bays // 2
            for side in (-1.0, 1.0):
                face = side * depth / 2.0
                if door:
                    w = bw * 0.5
                    sk, gl, mb = opening_bay("y", face, side, u0, u1, 0.0, RES_EAVE_CM,
                                             xc - w / 2, xc + w / 2, 2.0, 820.0 - w / 2, True)
                else:
                    w = bw * 0.42
                    sk, gl, mb = opening_bay("y", face, side, u0, u1, 0.0, RES_EAVE_CM,
                                             xc - w / 2, xc + w / 2, 210.0, 850.0, False)
                    oval = _arc(xc, 1010.0, 1.0, 0.0, 2 * math.pi, 16)[:-1]
                    oval = [(xc + (u - xc) * 70.0, 1010.0 + (z - 1010.0) * 50.0) for u, z in oval]
                    o0, o1 = sorted((face + side * SKIN_CM, face + side * (SKIN_CM + 10.0)))
                    mb = mb.merged(extrude_vertical(oval, "y", o0, o1))
                skin, glass, wtrim = skin.merged(sk), glass.merged(gl), wtrim.merged(mb)
    parts.append(("reservoir_hall/facade/walls", skin))
    parts.append(("reservoir_hall/windows", glass))
    parts.append(("reservoir_hall/window_trim/marble", wtrim))

    # 南北面逐间壁柱（铜版画南/北面：巨柱式通高）
    pil = mesh_mod.Mesh()
    for xa, xb, bays, depth in segs:
        bw = (xb - xa) / bays
        for k in range(bays + 1):
            for side in (-1.0, 1.0):
                pil = pil.merged(mesh_mod.box(PILASTER_W_CM, PILASTER_D_CM, PLINTH_H_CM,
                                              RES_EAVE_CM - CORNICE_H_CM, cx=xa + bw * k,
                                              cy=side * (depth / 2.0 + SKIN_CM + PILASTER_D_CM / 2.0)))
                pil = pil.merged(urn(xa + bw * k, side * (depth / 2.0 + SKIN_CM / 2.0),
                                     RES_EAVE_CM + RES_PARAPET_CM))                       # 女儿墙瓶饰
    parts.append(("reservoir_hall/pilasters/marble", pil))

    # 锡海：楼顶中段蓄水池（锡板池壁 + 水面）
    rim_l, rim_w = TIN_SEA_LEN_CM + 2 * TIN_RIM_CM, TIN_SEA_WID_CM + 2 * TIN_RIM_CM
    top = RES_EAVE_CM + TIN_SEA_DEPTH_CM + 20.0
    tin = polygon_ring([(-rim_l / 2, -rim_w / 2), (rim_l / 2, -rim_w / 2),
                        (rim_l / 2, rim_w / 2), (-rim_l / 2, rim_w / 2)], TIN_RIM_CM, RES_EAVE_CM, top)
    parts.append(("tin_sea/tin", tin))
    parts.append(("tin_sea/water", mesh_mod.box(TIN_SEA_LEN_CM, TIN_SEA_WID_CM,
                                                 RES_EAVE_CM + 10.0, RES_EAVE_CM + TIN_SEA_DEPTH_CM)))

    # 两端水车房（方亭式顶）
    for name, sx in (("waterwheel_house_west", -1.0), ("waterwheel_house_east", 1.0)):
        cx = sx * (RES_MID_LEN_CM / 2.0 + RES_END_LEN_CM / 2.0)
        parts.append((f"{name}/walls", mesh_mod.box(WHEEL_LEN_CM, WHEEL_WID_CM, RES_EAVE_CM,
                                                     RES_EAVE_CM + WHEEL_WALL_CM, cx=cx)))
        spec = (cx, 0.0, WHEEL_LEN_CM + 2 * ROOF_OVERHANG_CM, WHEEL_WID_CM + 2 * ROOF_OVERHANG_CM,
                RES_EAVE_CM + WHEEL_WALL_CM, WHEEL_ROOF_RISE_CM)
        parts.append((f"{name}/glazed_roof", hip_roof_xy(*spec)))
        parts.append((f"{name}/glazed_ridge", hip_ridges(*spec)))

    parts += _east_stairs()
    return parts


def _east_stairs() -> list[Part]:
    """东端阶台：三级台座 + 每级台前一跑石梯（内外交替折返，对称两侧），末跑达楼顶。"""
    face = RES_LEN_CM / 2.0
    tiers = mesh_mod.Mesh()
    steps = mesh_mod.Mesh()
    z_prev = 0.0
    for k, (depth, half, z_top) in enumerate(EAST_TIERS):
        tiers = tiers.merged(mesh_mod.box(depth, 2 * half, 0.0, z_top, cx=face + depth / 2.0))
        # 本跑位于本级台之前（东侧）的条带上，自 z_prev 升至 z_top
        x_band = face + depth + EAST_FLIGHT_DEPTH_CM / 2.0 if k == 0 else \
            face + depth + (EAST_TIERS[k - 1][0] - depth) / 2.0
        band_w = EAST_FLIGHT_DEPTH_CM if k == 0 else EAST_TIERS[k - 1][0] - depth
        outer = EAST_TIERS[0][1] if k == 0 else half
        for side in (-1.0, 1.0):
            ya, yb = (side * outer, side * 150.0) if k % 2 == 0 else (side * 150.0, side * outer)
            steps = steps.merged(flight(x_band, ya, x_band, yb, band_w, z_prev, z_top,
                                        EAST_STEPS_PER_FLIGHT, z_base=z_prev))
        z_prev = z_top
    return [("east_stairs/marble", tiers.merged(steps))]


def build_main_hall() -> list[Part]:
    """正楼：五段立面（翼楼 / 券窗段 / 中三间门罩）、两层门窗、汉白玉立柱与阳台、
    孔雀绿琉璃庑殿主顶与翼楼方亭式顶、门罩山花顶、南北下层平台小屋、楼后三间殿。"""
    parts: list[Part] = []
    cx = (MAIN_EAST_X + MAIN_WEST_X) / 2.0
    edges = [-MAIN_LEN_CM / 2.0]
    for w in MAIN_SEGMENTS_CM:
        edges.append(edges[-1] + w)

    walls = mesh_mod.box(MAIN_DEPTH_CM, MAIN_LEN_CM, 0.0, MAIN_EAVE_CM, cx=cx)
    for i in (0, 4):                                                         # 翼楼前凸
        walls = walls.merged(mesh_mod.box(PAVILION_PROJ_CM, MAIN_SEGMENTS_CM[i], 0.0, MAIN_EAVE_CM,
                                          cx=MAIN_WEST_X - PAVILION_PROJ_CM / 2.0,
                                          cy=(edges[i] + edges[i + 1]) / 2.0))
    walls = walls.merged(mesh_mod.box(FRONT_PROJ_CM, MAIN_SEGMENTS_CM[2], 0.0, MAIN_EAVE_CM,
                                      cx=MAIN_WEST_X - FRONT_PROJ_CM / 2.0))  # 中三间门罩
    parts.append(("front_building/walls", walls))
    parts += _frontispiece_crest()

    # 西立面墙皮逐间开洞：下层方窗；上层石刻券口窗（样式雷图说），中三间正中二层为正门
    skin, glass, sills = mesh_mod.Mesh(), mesh_mod.Mesh(), mesh_mod.Mesh()
    door_leaf, medals_g, medals_y = mesh_mod.Mesh(), mesh_mod.Mesh(), mesh_mod.Mesh()
    for i, (w, bays) in enumerate(zip(MAIN_SEGMENTS_CM, MAIN_SEGMENT_BAYS)):
        proj = PAVILION_PROJ_CM if i in (0, 4) else FRONT_PROJ_CM if i == 2 else 0.0
        x_face = MAIN_WEST_X - proj
        bw = w / bays
        for k in range(bays):
            u0, u1 = edges[i] + bw * k, edges[i] + bw * (k + 1)
            uc, ow = (u0 + u1) / 2.0, bw * 0.45
            door = i == 2 and k == 1
            storeys = [(0.0, FLOOR2_CM, uc - ow / 2, uc + ow / 2, 250.0, 650.0, False)]
            if door:
                storeys.append((FLOOR2_CM, MAIN_EAVE_CM, uc - 150.0, uc + 150.0, FLOOR2_CM + 2.0, 1180.0, True))
            else:
                storeys.append((FLOOR2_CM, MAIN_EAVE_CM, uc - ow / 2, uc + ow / 2, 950.0, 1170.0, True))
            for j, (z0, z1, ua, ub, zs, zh, arch) in enumerate(storeys):
                sk, gl, mb = opening_bay("x", x_face, -1.0, u0, u1, z0, z1, ua, ub, zs, zh, arch)
                skin, sills = skin.merged(sk), sills.merged(mb)
                if door and j == 1:
                    door_leaf = gl                                  # 正门：黄铜西洋雕花门（维基）
                else:
                    glass = glass.merged(gl)
            # 五色琉璃番花：下层窗上椭圆琉璃饰（绿、黄相间）
            oval = [(uc + 55.0 * math.cos(t), 740.0 + 38.0 * math.sin(t))
                    for t in (2 * math.pi * q / 16 for q in range(16))]
            o0, o1 = sorted((x_face - SKIN_CM, x_face - SKIN_CM - 8.0))
            medal = extrude_vertical(oval, "x", o0, o1)
            if (i + k) % 2:
                medals_y = medals_y.merged(medal)
            else:
                medals_g = medals_g.merged(medal)
    parts.append(("front_building/facade/walls", skin))
    parts.append(("front_building/windows", glass))
    parts.append(("front_building/window_trim/marble", sills))
    parts.append(("front_building/door/bronze", door_leaf))
    parts.append(("front_building/medallions_green/glazed_roof", medals_g))
    parts.append(("front_building/medallions_yellow/glazed_ridge", medals_y))

    # 汉白玉石作：门罩四柱、翼楼二层阳台、檐口露顶石栏杆
    marble = mesh_mod.Mesh()
    x_col = MAIN_WEST_X - FRONT_PROJ_CM - SKIN_CM - 45.0
    for y in (-520.0, -340.0, 340.0, 520.0):
        marble = marble.merged(mesh_mod.box(110.0, 110.0, FLOOR2_CM, FLOOR2_CM + 18.0, cx=x_col, cy=y))
        marble = marble.merged(lathe([(52, 0), (52, 6), (44, 14), (44, 18)], x_col, y, FLOOR2_CM + 18.0, seg=16))
        marble = marble.merged(lathe([(40, 0), (36, MAIN_EAVE_CM - CORNICE_H_CM - FLOOR2_CM - 110.0)],
                                     x_col, y, FLOOR2_CM + 36.0, seg=16))               # 收分柱身
        cap0 = MAIN_EAVE_CM - CORNICE_H_CM - 74.0
        marble = marble.merged(lathe([(37, 0), (44, 18), (52, 34)], x_col, y, cap0, seg=16))
        marble = marble.merged(mesh_mod.box(120.0, 120.0, cap0 + 34.0, cap0 + 74.0, cx=x_col, cy=y))  # 柱头
    for i in (0, 4):
        y0, y1 = edges[i] + 150.0, edges[i + 1] - 150.0
        xb = MAIN_WEST_X - PAVILION_PROJ_CM
        marble = marble.merged(mesh_mod.box(150.0, y1 - y0, FLOOR2_CM, FLOOR2_CM + 30.0,
                                            cx=xb - 75.0, cy=(y0 + y1) / 2.0))
        marble = marble.merged(balustrade(xb - 140.0, y0, xb - 140.0, y1, FLOOR2_CM + 30.0))
    for x in (MAIN_WEST_X + 10.0, MAIN_EAST_X - 10.0):                       # 檐上露顶石栏杆（维基）
        marble = marble.merged(balustrade(x, edges[1], x, edges[4], MAIN_EAVE_CM, 80.0))
    parts.append(("front_building/marble", marble))

    # 立面线脚：勒脚、二层腰线、檐口（汉白玉），西立面逐间壁柱（铜版画西面）
    outline = _main_outline(edges)
    trim = polygon_ring(outline, 2 * (SKIN_CM + 12.0), 0.0, PLINTH_H_CM)
    trim = trim.merged(polygon_ring(outline, 2 * (SKIN_CM + 10.0), FLOOR2_CM, FLOOR2_CM + 30.0))
    trim = trim.merged(polygon_ring(outline, 2 * (SKIN_CM + 25.0), MAIN_EAVE_CM - CORNICE_H_CM, MAIN_EAVE_CM))
    for i, (w, bays) in enumerate(zip(MAIN_SEGMENTS_CM, MAIN_SEGMENT_BAYS)):
        proj = PAVILION_PROJ_CM if i in (0, 4) else FRONT_PROJ_CM if i == 2 else 0.0
        x_face = MAIN_WEST_X - proj
        for k in range(bays + 1):
            y = edges[i] + w / bays * k
            for z0, z1 in ((PLINTH_H_CM, FLOOR2_CM), (FLOOR2_CM + 30.0, MAIN_EAVE_CM - CORNICE_H_CM)):
                trim = trim.merged(mesh_mod.box(PILASTER_D_CM, PILASTER_W_CM, z0, z1,
                                                cx=x_face - SKIN_CM - PILASTER_D_CM / 2.0, cy=y))
    parts.append(("front_building/trim/marble", trim))

    # 屋顶：通长庑殿主顶 + 两翼楼方亭式顶 + 门罩山花顶（孔雀绿琉璃瓦，脊为黄琉璃）
    roofs = [(cx, 0.0, MAIN_DEPTH_CM + 2 * ROOF_OVERHANG_CM, MAIN_LEN_CM + 2 * ROOF_OVERHANG_CM,
              MAIN_EAVE_CM, MAIN_ROOF_RISE_CM)]
    for i in (0, 4):
        roofs.append((cx - PAVILION_PROJ_CM / 2.0, (edges[i] + edges[i + 1]) / 2.0,
                      MAIN_DEPTH_CM + PAVILION_PROJ_CM + 2 * ROOF_OVERHANG_CM,
                      MAIN_SEGMENTS_CM[i] + 2 * ROOF_OVERHANG_CM, MAIN_EAVE_CM, PAVILION_ROOF_RISE_CM))
    roof, ridges = mesh_mod.Mesh(), mesh_mod.Mesh()
    for spec in roofs:
        roof = roof.merged(hip_roof_xy(*spec))
        ridges = ridges.merged(hip_ridges(*spec))
    parts.append(("front_building/glazed_roof", roof))
    parts.append(("front_building/glazed_ridge", ridges))
    fish = mesh_mod.Mesh()                                           # 垂脊四角翻尾石鱼（维基）
    hx, hy = (MAIN_DEPTH_CM + 2 * ROOF_OVERHANG_CM) / 2.0, (MAIN_LEN_CM + 2 * ROOF_OVERHANG_CM) / 2.0
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            x0, y0, z0 = cx + sx * hx, sy * hy, MAIN_EAVE_CM + 20.0
            pts = [(x0 - sx * 40.0, y0 - sy * 40.0, z0 + 15.0), (x0, y0, z0 + 20.0),
                   (x0 + sx * 25.0, y0 + sy * 25.0, z0 + 55.0), (x0 + sx * 10.0, y0 + sy * 10.0, z0 + 95.0)]
            for a, b in zip(pts, pts[1:]):
                fish = fish.merged(beam(a, b, 22.0))
    parts.append(("front_building/roof_fish/marble", fish))

    # 南北下层平台小屋（上建石栏杆）
    for name, sy in (("wing_south", -1.0), ("wing_north", 1.0)):
        yc = sy * (MAIN_LEN_CM / 2.0 + WING_LEN_CM / 2.0)
        parts.append((f"{name}/walls", mesh_mod.box(MAIN_DEPTH_CM, WING_LEN_CM, 0.0, FLOOR2_CM, cx=cx, cy=yc)))
        y_in, y_out = sy * MAIN_LEN_CM / 2.0, sy * (MAIN_LEN_CM / 2.0 + WING_LEN_CM)
        pts = [(MAIN_WEST_X, y_in), (MAIN_WEST_X, y_out), (MAIN_EAST_X, y_out), (MAIN_EAST_X, y_in)]
        rail = mesh_mod.Mesh()
        for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
            rail = rail.merged(balustrade(xa, ya, xb, yb, FLOOR2_CM))
        parts.append((f"{name}/marble", rail))

    # 楼后三间殿（连接蓄水楼，上为平台）
    parts.append(("rear_hall/walls", mesh_mod.box(REAR_GAP_CM, 1400.0, 0.0, FLOOR2_CM,
                                                  cx=MAIN_EAST_X + REAR_GAP_CM / 2.0)))
    return parts


def _frontispiece_crest() -> list[Part]:
    """中三间门罩上的巴洛克山花（铜版画西面；样式雷「门罩上冲天花栏杆…琉璃番花葫芦顶」）。

    轮廓：两端内卷的凹弧肩部 → 中段弓形顶；沿顶边汉白玉线脚，正中椭圆花框，肩部与顶上瓶饰。
    """
    half = MAIN_SEGMENTS_CM[2] / 2.0
    base = MAIN_EAVE_CM
    shoulder_y, shoulder_z = 520.0, base + 320.0
    top_z = CREST_TOP_CM

    def z_at(y: float) -> float:
        a = abs(y)
        if a >= shoulder_y:                                       # 凹弧肩部：外低内高
            t = (half - a) / (half - shoulder_y)
            return base + 40.0 + (shoulder_z - base - 40.0) * (1 - math.cos(t * math.pi / 2))
        t = a / shoulder_y                                        # 中段弓形
        return top_z - (top_z - shoulder_z) * (1 - math.cos(t * math.pi / 2)) ** 1.5

    ys = [-half + 2 * half * k / 48 for k in range(49)]
    outline = [(y, z_at(y)) for y in ys] + [(half, base), (-half, base)]
    x0 = MAIN_WEST_X - FRONT_PROJ_CM - SKIN_CM - 10.0
    wall = extrude_vertical(outline, "x", x0, x0 + 70.0)
    trim = mesh_mod.Mesh()
    for (ya, za), (yb, zb) in zip(outline[:48], outline[1:49]):  # 顶边线脚
        trim = trim.merged(beam((x0 - 12.0, ya, za + 6.0), (x0 - 12.0, yb, zb + 6.0), 22.0))
    oval = [(110.0 * math.cos(t), base + 230.0 + 140.0 * math.sin(t)) for t in (2 * math.pi * q / 20 for q in range(20))]
    trim = trim.merged(extrude_vertical(oval, "x", x0 - 14.0, x0))
    ring = oval + oval[:1]
    for (ya, za), (yb, zb) in zip(ring, ring[1:]):                # 花框
        trim = trim.merged(beam((x0 - 18.0, ya, za), (x0 - 18.0, yb, zb), 14.0))
    for y in (-half + 40.0, -shoulder_y, shoulder_y, half - 40.0):
        trim = trim.merged(urn(x0 + 30.0, y, z_at(y) - 4.0, 1.3))
    trim = trim.merged(urn(x0 + 30.0, 0.0, top_z - 6.0, 2.0))      # 葫芦顶
    return [("front_building/crest/walls", wall), ("front_building/crest/marble", trim)]


def _stone_leopards(x_front: float) -> list[Part]:
    """正门前西洋石豹一对，口中吐水沿阶叠落（维基「石豹两只，口中吐水」）。蹲踞姿，简化形体。"""
    body = mesh_mod.Mesh()
    jets: list[Part] = []
    for name, s in (("south", -1.0), ("north", 1.0)):
        y = s * 300.0
        x = x_front - 60.0
        z = FLOOR2_CM
        body = body.merged(mesh_mod.box(70.0, 60.0, z, z + 40.0, cx=x + 20.0, cy=y))           # 座
        body = body.merged(beam((x + 45.0, y, z + 75.0), (x - 30.0, y, z + 95.0), 40.0))       # 躯干
        body = body.merged(beam((x - 30.0, y, z + 40.0), (x - 30.0, y, z + 100.0), 22.0))      # 前腿
        body = body.merged(lathe([(15, 0), (19, 12), (17, 26), (9, 34)], x - 52.0, y, z + 92.0, seg=10))  # 首
        body = body.merged(beam((x + 55.0, y, z + 70.0), (x + 80.0, y, z + 115.0), 9.0))       # 尾
        mouth = (x - 70.0, y, z + 105.0)
        jets.append((f"stone_leopard_{name}/jet", jet(mouth, (x - 190.0, y * 1.4, z))))
    return [("stone_leopards/marble", body)] + jets


def _main_outline(edges: list[float]) -> list[tuple[float, float]]:
    """正楼平面外轮廓（逆时针）：东墙直、西立面两端翼楼与中三间门罩前凸。"""
    e, w = MAIN_EAST_X, MAIN_WEST_X
    wp, wc = w - PAVILION_PROJ_CM, w - FRONT_PROJ_CM
    return [(e, edges[0]), (e, edges[5]), (wp, edges[5]), (wp, edges[4]), (w, edges[4]), (w, edges[3]),
            (wc, edges[3]), (wc, edges[2]), (w, edges[2]), (w, edges[1]), (wp, edges[1]), (wp, edges[0])]


def build_front_court() -> list[Part]:
    """楼前：二层门前平台、叠落石跑梯（导水台）、菱形生肖池、十二生肖像、石蚌、喷水塔、八角石鼎、广场铺地。"""
    parts: list[Part] = []
    x_land0 = MAIN_WEST_X - FRONT_PROJ_CM                    # 门罩西面
    x_land1 = x_land0 - LANDING_DEPTH_CM
    stairs = mesh_mod.box(LANDING_DEPTH_CM, 2 * LANDING_HALF_CM, 0.0, FLOOR2_CM,
                          cx=(x_land0 + x_land1) / 2.0)       # 二层门前平台
    rails = mesh_mod.Mesh()
    cascade = mesh_mod.Mesh()
    band_x = x_land1 + STAIR_W_CM / 2.0                       # 上跑贴楼前，梯中线 x
    for s in (-1.0, 1.0):
        # 上跑：沿楼南北向外下行
        y0, y1 = s * LANDING_HALF_CM, s * UPPER_RUN_END_CM
        stairs = stairs.merged(flight(band_x, y0, band_x, y1, STAIR_W_CM, FLOOR2_CM, MID_LANDING_Z_CM, UPPER_STEPS))
        rails = rails.merged(stepped_balustrade(x_land1, y0, x_land1, y1, FLOOR2_CM, MID_LANDING_Z_CM, UPPER_STEPS))
        # 转折平台
        ym = s * (UPPER_RUN_END_CM + MID_LANDING_CM / 2.0)
        stairs = stairs.merged(mesh_mod.box(STAIR_W_CM, MID_LANDING_CM, 0.0, MID_LANDING_Z_CM, cx=band_x, cy=ym))
        # 下跑：折向西落地，内侧（池侧）设导水台
        xa, xb = x_land1, x_land1 - LOWER_RUN_CM
        stairs = stairs.merged(flight(xa, ym, xb, ym, MID_LANDING_CM, MID_LANDING_Z_CM, 0.0, LOWER_STEPS))
        y_out = ym + s * (MID_LANDING_CM / 2.0 - RAIL_T_CM / 2.0)
        rails = rails.merged(stepped_balustrade(xa, y_out, xb, y_out, MID_LANDING_Z_CM, 0.0, LOWER_STEPS))
        y_in = ym - s * (MID_LANDING_CM / 2.0 + CASCADE_W_CM / 2.0)
        for k in range(LOWER_STEPS):                          # 每级一导水台（每侧 30，两侧 60）
            t0, t1 = k / LOWER_STEPS, (k + 1) / LOWER_STEPS
            top = MID_LANDING_Z_CM * (1.0 - (k + 0.5) / LOWER_STEPS)
            cascade = cascade.merged(obox(xa + (xb - xa) * t0, y_in, xa + (xb - xa) * t1, y_in,
                                          CASCADE_W_CM, 0.0, top + 25.0))
    parts.append(("west_stairs/marble", stairs.merged(rails)))
    parts += _stone_leopards(x_land1 + LANDING_DEPTH_CM)
    parts.append(("west_stairs/cascade", cascade))

    # 生肖池：后缘石蚌龛、八字两墙、前缘外凸弧（「菱形」）
    pool = _pool_outline()
    parts.append(("zodiac_pool/marble", polygon_ring(pool, POOL_WALL_T_CM, POOL_FLOOR_CM, POOL_CURB_CM)
                  .merged(terrain_mod.polygon_slab(pool, z_top=POOL_FLOOR_CM, depth=10.0))))
    parts.append(("zodiac_pool/water", terrain_mod.polygon_slab(pool, z_top=POOL_WATER_CM, depth=5.0)))
    shell = mesh_mod.box(150.0, 800.0, POOL_FLOOR_CM, 60.0, cx=SHELL_X)                  # 假山座
    for dy, h, w in ((-260.0, 110.0, 160.0), (240.0, 95.0, 180.0), (-40.0, 140.0, 220.0)):
        shell = shell.merged(mesh_mod.box(120.0, w, 60.0, 60.0 + h, cx=SHELL_X - 20.0, cy=dy))
    fan = []
    for k in range(37):                                                   # 扇贝外缘：九瓣起伏
        t = math.pi * k / 36
        r = SHELL_H_CM * (1.0 + 0.07 * math.cos(9 * t))
        fan.append((r * math.cos(t), 60.0 + r * math.sin(t)))
    shell = shell.merged(extrude_vertical(fan, "x", SHELL_X - 25.0, SHELL_X + 10.0))
    parts.append(("zodiac_pool/shell/marble", shell))
    tower = mesh_mod.cylinder(POOL_FLOOR_CM, 60.0, 180.0, FOUNTAIN_X, 0.0, 16)
    tower = tower.merged(mesh_mod.cylinder(60.0, 260.0, 40.0, FOUNTAIN_X, 0.0, 12))
    tower = tower.merged(mesh_mod.cylinder(260.0, 300.0, 80.0, FOUNTAIN_X, 0.0, 16))
    parts.append(("zodiac_pool/center_fountain/marble", tower))
    parts.append(("zodiac_pool/center_fountain/jet", jet((FOUNTAIN_X, 0.0, 300.0), (FOUNTAIN_X, 0.0, 650.0))))

    seated = sculpt.load_figure_assets(SEATED_ASSET_DIR)
    # 十二生肖：沿八字墙外侧各六，由内（东）向外（西）
    xa, ya, xb, yb = POOL_BACK_X, POOL_BACK_HALF_CM, POOL_SHOULDER_X, POOL_HALF_CM
    seg = math.hypot(xb - xa, yb - ya)
    nx, ny = -(yb - ya) / seg, (xb - xa) / seg                # +Y 侧墙的外法向（指向池外）
    if ny < 0:
        nx, ny = -nx, -ny
    for names, s in ((ZODIAC_SOUTH, -1.0), (ZODIAC_NORTH, 1.0)):
        for k, name in enumerate(names):
            t = 0.12 + 0.76 * k / (len(names) - 1)
            x = xa + (xb - xa) * t + nx * ZODIAC_OFFSET_CM
            y = s * (ya + (yb - ya) * t + ny * ZODIAC_OFFSET_CM)
            body = mesh_mod.box(PLINTH_CM, PLINTH_CM, 0.0, 20.0, cx=x, cy=y)                 # 座：底、身、顶
            body = body.merged(mesh_mod.box(PLINTH_CM - 16.0, PLINTH_CM - 16.0, 20.0, PLINTH_H_CM - 15.0, cx=x, cy=y))
            body = body.merged(mesh_mod.box(PLINTH_CM, PLINTH_CM, PLINTH_H_CM - 15.0, PLINTH_H_CM, cx=x, cy=y))
            zb = PLINTH_H_CM
            land = (x + (FOUNTAIN_X - x) * 0.3, y * 0.45, POOL_WATER_CM)
            fd = math.hypot(land[0] - x, land[1] - y)
            face = ((land[0] - x) / fd, (land[1] - y) / fd)              # 坐像与兽首朝池心方向喷水
            m, mouth_local = sculpt.animal_head(name)                      # 铜铸兽首（照片生成 / 雕塑，sculpt.py）
            if seated:                                                    # 遗址整像复制品照片生成的盘坐袍服身躯：兽首插入颈口
                torso, head_l, mouth_l = sculpt.attach_head(seated[k % len(seated)][0], SEATED_NECK, m, mouth_local)
                body = body.merged(sculpt.place(torso, x, y, zb, face, SEATED_HEIGHT_CM))
                head = sculpt.place(head_l, x, y, zb, face, SEATED_HEIGHT_CM)
                mouth = sculpt.place_point(mouth_l, x, y, zb, face, SEATED_HEIGHT_CM)
            else:                                                         # 后备：雕塑袍服坐像（sculpt.py）
                fs = FIGURE_H_CM / sculpt.ROBE_HEIGHT
                body = body.merged(sculpt.robed_body(x, y, zb, face, fs))
                zh = zb + (sculpt.ROBE_HEIGHT - 6.0) * fs
                head = sculpt.place(m, x, y, zh, face, HEAD_SCALE)
                mouth = sculpt.place_point(mouth_local, x, y, zh, face, HEAD_SCALE)
            parts.append((f"zodiac_{name}/marble", body))
            parts.append((f"zodiac_{name}/bronze", head))
            parts.append((f"zodiac_{name}/jet", jet(mouth, land)))

    # 八角石鼎（梯脚外，一对）
    for name, s in (("stone_urn_south", -1.0), ("stone_urn_north", 1.0)):
        ux, uy = URN_POS[0], s * URN_POS[1]
        ped = lathe([(URN_PEDESTAL_R_CM + 15, 0), (URN_PEDESTAL_R_CM + 15, 25), (URN_PEDESTAL_R_CM, 35),
                     (URN_PEDESTAL_R_CM, URN_PEDESTAL_H_CM - 30), (URN_PEDESTAL_R_CM + 15, URN_PEDESTAL_H_CM - 15),
                     (URN_PEDESTAL_R_CM + 15, URN_PEDESTAL_H_CM)], ux, uy, 0.0, seg=8, phase_deg=22.5)
        vase = lathe(_scaled([(40, 0), (40, 15), (30, 30), (55, 80), (75, 140), (60, 200), (35, 225),
                              (45, 240), (20, 255), (8, 260)], URN_R_CM / 75.0, URN_H_CM / 260.0),
                     ux, uy, URN_PEDESTAL_H_CM, seg=8, phase_deg=22.5)       # 八角石鼎（八棱）
        parts.append((f"{name}/marble", ped.merged(vase)))

    # 楼前广场铺地：避开水池外包，分四块
    px0, px1 = POOL_FRONT_X, POOL_BACK_X
    pave = mesh_mod.box(px0 - COURT_WEST_X, 2 * COURT_HALF_CM, -5.0, 0.0, cx=(COURT_WEST_X + px0) / 2.0)
    pave = pave.merged(mesh_mod.box(x_land1 - px1, 2 * COURT_HALF_CM, -5.0, 0.0, cx=(px1 + x_land1) / 2.0))
    for s in (-1.0, 1.0):
        pave = pave.merged(mesh_mod.box(px1 - px0, COURT_HALF_CM - POOL_HALF_CM, -5.0, 0.0,
                                        cx=(px0 + px1) / 2.0, cy=s * (COURT_HALF_CM + POOL_HALF_CM) / 2.0))
    # 池外包之内、池外的空隙：前角（弧外）与后角（八字墙外）各一块，南北镜像
    arc = [pt for pt in pool if pt[0] < POOL_SHOULDER_X - 1e-6 and pt[1] > 0]   # 北半前缘弧点（自北向西）
    for s in (-1.0, 1.0):
        front = [(px0, s * POOL_HALF_CM), (POOL_SHOULDER_X, s * POOL_HALF_CM)]
        front += [(x, s * y) for (x, y) in arc] + [(px0, 0.0)]
        back = [(POOL_SHOULDER_X, s * POOL_HALF_CM), (px1, s * POOL_HALF_CM), (px1, s * POOL_BACK_HALF_CM)]
        for poly in (front, back):
            if s > 0:
                poly = poly[::-1]                                     # 保持逆时针
            pave = pave.merged(terrain_mod.polygon_slab(poly, z_top=0.0, depth=5.0))
    parts.append(("court/paving", pave))
    return parts


def _pool_outline() -> list[tuple[float, float]]:
    """生肖池平面（逆时针）：后缘龛 → 北八字墙 → 前缘外凸弧 → 南八字墙。"""
    pts = [(POOL_BACK_X, -POOL_BACK_HALF_CM), (POOL_BACK_X, POOL_BACK_HALF_CM),
           (POOL_SHOULDER_X, POOL_HALF_CM)]
    depth = POOL_SHOULDER_X - POOL_FRONT_X
    for k in range(1, POOL_ARC_SEGMENTS):
        t = math.pi / 2.0 - math.pi * k / POOL_ARC_SEGMENTS             # 90° → −90°（北 → 西 → 南）
        pts.append((POOL_SHOULDER_X - depth * math.cos(t), POOL_HALF_CM * math.sin(t)))
    pts.append((POOL_SHOULDER_X, -POOL_HALF_CM))
    return pts


def build_garden_fountains() -> list[Part]:
    """蓄水楼南北：两端各一八角池（共四）、中央各一圆形喷泉（共二）。"""
    parts: list[Part] = []
    x_end = RES_MID_LEN_CM / 2.0 + RES_END_LEN_CM / 2.0
    for side_name, s in (("south", -1.0), ("north", 1.0)):
        y = s * GARDEN_FOUNTAIN_Y
        for pos_name, x, n, r in (("west", -x_end, 8, OCTAGON_R_CM), ("center", 0.0, 16, ROUND_R_CM),
                                  ("east", x_end, 8, OCTAGON_R_CM)):
            pts = regular_polygon(x, y, r, n, 22.5 if n == 8 else 0.0)
            name = f"fountain_{side_name}_{pos_name}"
            parts.append((f"{name}/marble", polygon_ring(pts, 40.0, 0.0, FOUNTAIN_CURB_CM)
                          .merged(mesh_mod.cylinder(0.0, 180.0, 30.0, x, y, 8))))
            parts.append((f"{name}/water", mesh_mod.prism(pts, 0.0, FOUNTAIN_CURB_CM - 15.0)))
            parts.append((f"{name}/jet", jet((x, y, 180.0), (x, y, 380.0))))

    # 层叠修剪树（铜版画南/北面：楼前园中成行的层叠圆锥树），避开喷水池
    fx = (-x_end, 0.0, x_end)
    for side_name, s in (("south", -1.0), ("north", 1.0)):
        crowns, trunks = mesh_mod.Mesh(), mesh_mod.Mesh()
        for row_y in (RES_END_DEPTH_CM / 2.0 + 450.0, GARDEN_FOUNTAIN_Y, GARDEN_FOUNTAIN_Y + 700.0):
            for k in range(-4, 5):
                x = k * 620.0
                if abs(row_y - GARDEN_FOUNTAIN_Y) < 1.0 and min(abs(x - f) for f in fx) < 500.0:
                    continue
                c, t = topiary(x, s * row_y)
                crowns, trunks = crowns.merged(c), trunks.merged(t)
        parts.append((f"topiary_{side_name}/foliage", crowns))
        parts.append((f"topiary_{side_name}/bark", trunks))
    return parts


def build_haiyantang_scene() -> list[Part]:
    """海晏堂景：正楼 + 楼前石梯水池 + 工字蓄水楼 + 南北喷水池。"""
    return build_main_hall() + build_front_court() + build_reservoir_hall() + build_garden_fountains()


# ===========================================================================
# 远瀛观 · 大水法 · 观水法（research-yuanyingguan-dashuifa.md；推测项 S-041）
# 局部坐标：+X 东、+Y 北，原点 = OSM「大水法」POI；三者南北一线（北远瀛观、中大水法、南观水法）
# ===========================================================================

# 远瀛观高台（OSM 遗址轮廓北段约 45 × 41 m）
YY_TERRACE_HALF_CM = 2250.0
YY_TERRACE_Y0, YY_TERRACE_Y1 = 700.0, 4800.0
YY_TERRACE_H_CM = 300.0          # 高台高（工作假设）
YY_STAIR_X = (1350.0, 1750.0)    # 台前东西弧形石梯（简化为直跑）所在 |x| 区间
YY_STAIR_RUN_CM = 600.0
YY_STAIR_STEPS = 20

# 远瀛观主楼：倒凹字形（南向开口），主体 30 × 16 m，两翼前凸 4 m（铜版画十四比例）
YY_HALF_CM = 1500.0
YY_BODY_Y0, YY_BODY_Y1 = 2700.0, 4300.0
YY_WING_X0 = 900.0               # 翼楼内侧 |x|
YY_WING_Y0 = 2300.0              # 翼楼南端
YY_BODY_EAVE_CM = 700.0          # 主体檐高（台面起算）
YY_WING_EAVE_CM = 870.0          # 翼楼檐高（高于主体，铜版画）
YY_CENTER_HALF_CM = 400.0        # 中央钟楼式高起部分半宽
YY_CENTER_TOP_CM = 1150.0        # 中央高起墙顶
YY_CUPOLA_CM = 320.0             # 翼楼顶钟亭见方

# 大水法：石龛 + 两侧壁柱 + 卷涡翼墙 + 七级水台 + 半圆海棠池 + 铜鹿 + 十犬 + 东西十三层喷水塔
DSF_BACK_Y = YY_TERRACE_Y0       # 石龛背靠高台南壁
DSF_NICHE_HALF_CM = 200.0
DSF_NICHE_H_CM = 1200.0
DSF_CREST_CM = 1450.0
DSF_PYLON_X = (300.0, 520.0)
DSF_PYLON_H_CM = 870.0
DSF_WING_OUT_CM = 1000.0         # 卷涡翼墙外端 |x|（翼展约 20 m）
DSF_CASCADE_TIERS = 7            # 七级水台（维基，medium）
DSF_POOL_RX, DSF_POOL_RY = 950.0, 900.0
DSF_POOL_Y = DSF_BACK_Y - 150.0
DSF_HOUNDS_PER_SIDE = 5          # 鹿东西各五犬（medium）
DSF_TOWER_X, DSF_TOWER_Y = 1900.0, -600.0
DSF_TOWER_TIERS = 13             # 十三层（medium）
DSF_TOWER_BASIN_R = 450.0
DSF_TOWER_JETS = 8               # 池底大喷水管八根（维基，medium）；水射高六尺≈1.9 m

# 观水法（坐南朝北）：平台、弧形石屏五件、宝座、铜鹤、方塔、鼎炉、东西巴洛克门
GSF_Y = -3100.0                  # OSM 观水法 POI 在大水法南约 31 m
GSF_HALF_CM = 1100.0             # 门到门约 22 m（铜版画十六比例）
GSF_PLATFORM_H_CM = 120.0
GSF_SCREEN_CHORD_CM = 830.0      # 屏风弦长 8.3 m（百科转引「长 8.3 米」，low）
GSF_SCREEN_SAG_CM = 150.0
GSF_SCREEN_H_CM = 400.0
GSF_SCREEN_PANELS = 5            # 屏心五件（medium）

PLAZA_HALF_CM = 2400.0


def _half_disc(cy: float, r: float, z0: float, z1: float, n: int = 16, sign: float = -1.0) -> mesh_mod.Mesh:
    """以 (0, cy) 为心的半圆台（sign=−1 朝南）。"""
    pts = [(r * math.cos(math.pi * k / n), cy + sign * r * math.sin(math.pi * k / n)) for k in range(n + 1)]
    if sign < 0:
        pts = pts[::-1]
    return mesh_mod.prism(pts, z0, z1)


def _sloped_wing(x_inner: float, x_outer: float, y: float, thick: float, z_high: float, z_low: float) -> mesh_mod.Mesh:
    """卷涡翼墙：自内端 z_high 斜降至外端 z_low（沿 X 的楔形体）。"""
    length = abs(x_outer - x_inner)
    w = mesh_mod.wedge(thick, length, 0.0, z_high, z_low)        # 顶面沿 Y：+Y 高、−Y 低
    angle = 90.0 if x_outer > x_inner else -90.0                  # 把 +Y（高端）转向内侧
    return w.rotated_z(angle).translated(dx=(x_inner + x_outer) / 2.0, dy=y)


def _lobed_half_pool(cy: float, rx: float, ry: float, lobes: int = 4, n: int = 32) -> list[tuple[float, float]]:
    """半圆海棠形池（南半）：椭圆加花瓣起伏，北缘为直边（逆时针）。"""
    pts = []
    for k in range(n + 1):
        t = math.pi + math.pi * k / n                              # 180° → 360°（西 → 南 → 东）
        bump = 1.0 + 0.07 * math.cos(lobes * 2 * (t - math.pi))
        pts.append((rx * bump * math.cos(t), cy + ry * bump * math.sin(t)))
    return pts


def build_yuanyingguan() -> list[Part]:
    """远瀛观：高台（栏杆、台前石梯）+ 倒凹字形主楼（两层庑殿顶、中央钟窗、翼楼钟亭）。"""
    parts: list[Part] = []
    zt = YY_TERRACE_H_CM
    h = YY_TERRACE_HALF_CM
    terrace = mesh_mod.box(2 * h, YY_TERRACE_Y1 - YY_TERRACE_Y0, 0.0, zt,
                           cy=(YY_TERRACE_Y0 + YY_TERRACE_Y1) / 2.0)
    for s in (-1.0, 1.0):                                          # 台前东西石梯（南下）
        xc = s * sum(YY_STAIR_X) / 2.0
        terrace = terrace.merged(flight(xc, YY_TERRACE_Y0, xc, YY_TERRACE_Y0 - YY_STAIR_RUN_CM,
                                        YY_STAIR_X[1] - YY_STAIR_X[0], zt, 0.0, YY_STAIR_STEPS))
    rail = polygon_ring([(-h, YY_TERRACE_Y0), (h, YY_TERRACE_Y0), (h, YY_TERRACE_Y1), (-h, YY_TERRACE_Y1)],
                        RAIL_T_CM, zt, zt + RAIL_H_CM)
    parts.append(("yuanyingguan_terrace/marble", terrace.merged(rail)))

    # 主楼墙体：主体 + 两翼前凸 + 中央钟楼式高起 + 翼楼顶钟亭
    body_cy = (YY_BODY_Y0 + YY_BODY_Y1) / 2.0
    walls = mesh_mod.box(2 * YY_HALF_CM, YY_BODY_Y1 - YY_BODY_Y0, zt, zt + YY_BODY_EAVE_CM, cy=body_cy)
    wing_cx = (YY_WING_X0 + YY_HALF_CM) / 2.0
    wing_w = YY_HALF_CM - YY_WING_X0
    for s in (-1.0, 1.0):
        walls = walls.merged(mesh_mod.box(wing_w, YY_BODY_Y1 - YY_WING_Y0, zt, zt + YY_WING_EAVE_CM,
                                          cx=s * wing_cx, cy=(YY_WING_Y0 + YY_BODY_Y1) / 2.0))
        walls = walls.merged(mesh_mod.box(YY_CUPOLA_CM, YY_CUPOLA_CM, zt + YY_WING_EAVE_CM + 250.0,
                                          zt + YY_WING_EAVE_CM + 250.0 + YY_CUPOLA_CM,
                                          cx=s * wing_cx, cy=(YY_WING_Y0 + YY_BODY_Y1) / 2.0))
    walls = walls.merged(mesh_mod.box(2 * YY_CENTER_HALF_CM, 600.0, zt + YY_BODY_EAVE_CM, zt + YY_CENTER_TOP_CM,
                                      cy=YY_BODY_Y0 + 300.0))      # 中央钟楼式山花墙
    parts.append(("yuanyingguan/walls", walls))

    # 门窗：中三间（圆光门 + 两券门）、两翼正面窗、中央圆形钟窗与翼楼钟亭圆窗
    win = mesh_mod.Mesh()
    for x, w, z1 in ((0.0, 260.0, 520.0), (-450.0, 200.0, 480.0), (450.0, 200.0, 480.0)):
        win = win.merged(_panel_y(YY_BODY_Y0, x, w, zt, zt + z1, -1.0))
    for s in (-1.0, 1.0):
        win = win.merged(_panel_y(YY_WING_Y0, s * wing_cx, 220.0, zt + 120.0, zt + 560.0, -1.0))
        win = win.merged(_panel_y(YY_WING_Y0 + (YY_BODY_Y1 - YY_WING_Y0) / 2.0 - YY_CUPOLA_CM / 2.0,
                                  s * wing_cx, 120.0, zt + YY_WING_EAVE_CM + 350.0,
                                  zt + YY_WING_EAVE_CM + 470.0, -1.0))
    win = win.merged(_panel_y(YY_BODY_Y0, 0.0, 200.0, zt + YY_BODY_EAVE_CM + 100.0,
                              zt + YY_BODY_EAVE_CM + 300.0, -1.0))   # 券上圆形钟窗（方板示意）
    parts.append(("yuanyingguan/windows", win))

    # 汉白玉：门旁雕花石柱一对 + 石狮一对
    marble = mesh_mod.Mesh()
    for s in (-1.0, 1.0):
        marble = marble.merged(mesh_mod.cylinder(zt, zt + YY_BODY_EAVE_CM, 45.0, s * 230.0, YY_BODY_Y0 - 70.0, 12))
        marble = marble.merged(mesh_mod.box(70.0, 120.0, zt, zt + 130.0, cx=s * 330.0, cy=YY_BODY_Y0 - 250.0))
    parts.append(("yuanyingguan/marble", marble))

    # 屋顶：主体下层鱼鳞金瓦庑殿、中央上层琉璃顶、翼楼庑殿与钟亭小顶
    gold = hip_roof_xy(0.0, body_cy, 2 * YY_HALF_CM + 120.0, YY_BODY_Y1 - YY_BODY_Y0 + 120.0,
                       zt + YY_BODY_EAVE_CM, 250.0)
    parts.append(("yuanyingguan/gold_roof", gold))
    glazed = hip_roof_xy(0.0, YY_BODY_Y0 + 700.0, 2 * YY_CENTER_HALF_CM + 200.0, 1000.0,
                         zt + YY_CENTER_TOP_CM, 380.0)
    for s in (-1.0, 1.0):
        cy = (YY_WING_Y0 + YY_BODY_Y1) / 2.0
        glazed = glazed.merged(hip_roof_xy(s * wing_cx, cy, wing_w + 120.0, YY_BODY_Y1 - YY_WING_Y0 + 120.0,
                                           zt + YY_WING_EAVE_CM, 250.0))
        glazed = glazed.merged(hip_roof_xy(s * wing_cx, cy, YY_CUPOLA_CM + 80.0, YY_CUPOLA_CM + 80.0,
                                           zt + YY_WING_EAVE_CM + 250.0 + YY_CUPOLA_CM, 200.0))
    parts.append(("yuanyingguan/glazed_roof", glazed))
    return parts


def build_dashuifa() -> list[Part]:
    """大水法：石龛与壁柱、卷涡翼墙、狮子头、七级水台、半圆海棠池、铜鹿与十犬、东西十三层喷水塔。"""
    parts: list[Part] = []
    yb = DSF_BACK_Y
    niche = mesh_mod.box(2 * DSF_NICHE_HALF_CM, 150.0, 0.0, DSF_NICHE_H_CM, cy=yb - 75.0)
    niche = niche.merged(mesh_mod.box(2 * DSF_NICHE_HALF_CM + 60.0, 160.0, DSF_NICHE_H_CM, DSF_CREST_CM - 80.0,
                                      cy=yb - 80.0))
    niche = niche.merged(mesh_mod.box(160.0, 120.0, DSF_CREST_CM - 80.0, DSF_CREST_CM, cy=yb - 80.0))   # 贝壳顶饰
    for s in (-1.0, 1.0):
        x0, x1 = DSF_PYLON_X
        niche = niche.merged(mesh_mod.box(x1 - x0, 300.0, 0.0, DSF_PYLON_H_CM, cx=s * (x0 + x1) / 2.0, cy=yb - 150.0))
        niche = niche.merged(mesh_mod.cylinder(DSF_PYLON_H_CM, DSF_PYLON_H_CM + 280.0, 50.0,
                                               s * (x0 + x1) / 2.0, yb - 150.0, 12))       # 壁柱顶瓶饰
        niche = niche.merged(_sloped_wing(s * x1, s * DSF_WING_OUT_CM, yb - 150.0, 120.0, 700.0, 60.0))
    parts.append(("dashuifa_niche/marble", niche))
    parts.append(("dashuifa_niche/windows", _panel_y(yb - 150.0, 0.0, 240.0, 100.0, 1000.0, -1.0)))
    parts.append(("dashuifa_niche/bronze", mesh_mod.box(70.0, 50.0, 820.0, 900.0, cy=yb - 180.0)))  # 狮子头
    parts.append(("dashuifa_niche/jet", jet((0.0, yb - 210.0, 850.0), (0.0, yb - 300.0, 430.0))))

    # 七级水台：自石龛前逐级外扩下降
    tiers = mesh_mod.Mesh()
    for k in range(DSF_CASCADE_TIERS):
        r = 120.0 + 40.0 * k
        tiers = tiers.merged(_half_disc(yb - 150.0, r, 0.0, 420.0 - 55.0 * k))
    parts.append(("dashuifa_cascade/cascade", tiers))

    # 半圆海棠池
    pool = _lobed_half_pool(DSF_POOL_Y, DSF_POOL_RX, DSF_POOL_RY)
    parts.append(("dashuifa_pool/marble", polygon_ring(pool, POOL_WALL_T_CM, POOL_FLOOR_CM, POOL_CURB_CM)
                  .merged(terrain_mod.polygon_slab(pool, z_top=POOL_FLOOR_CM, depth=10.0))))
    parts.append(("dashuifa_pool/water", terrain_mod.polygon_slab(pool, z_top=POOL_WATER_CM, depth=5.0)))

    # 铜鹿（池心南向）与东西各五猎犬（喷水射鹿）
    deer_y = DSF_POOL_Y - 0.62 * DSF_POOL_RY
    deer = mesh_mod.box(60.0, 130.0, POOL_WATER_CM, 140.0, cy=deer_y)
    deer = deer.merged(mesh_mod.box(90.0, 20.0, 140.0, 200.0, cy=deer_y + 50.0))      # 鹿角（八杈示意）
    parts.append(("deer/bronze", deer))
    parts.append(("deer/jet", jet((0.0, deer_y + 50.0, 200.0), (0.0, deer_y + 50.0, 480.0))))   # 鹿角八杈喷水
    for name, s in (("hounds_west", -1.0), ("hounds_east", 1.0)):
        hounds = mesh_mod.Mesh()
        for k in range(DSF_HOUNDS_PER_SIDE):
            a = math.radians(200.0 + 12.0 * k) if s < 0 else math.radians(340.0 - 12.0 * k)
            hx, hy = 0.82 * DSF_POOL_RX * math.cos(a), DSF_POOL_Y + 0.82 * DSF_POOL_RY * math.sin(a)
            hounds = hounds.merged(mesh_mod.box(40.0, 80.0, POOL_WATER_CM, 70.0, cx=hx, cy=hy))
            parts.append((f"{name}_{k + 1}/jet", jet((hx, hy, 60.0), (hx * 0.12, deer_y, 110.0))))   # 十犬喷鹿
        parts.append((f"{name}/bronze", hounds))

    # 东西十三层方形喷水塔（各在池中，池底八喷管）
    for name, s in (("fountain_tower_west", -1.0), ("fountain_tower_east", 1.0)):
        tx, ty = s * DSF_TOWER_X, DSF_TOWER_Y
        basin = [(tx + DSF_TOWER_BASIN_R * (1 + 0.12 * math.cos(4 * t)) * math.cos(t),
                  ty + DSF_TOWER_BASIN_R * (1 + 0.12 * math.cos(4 * t)) * math.sin(t))
                 for t in (2 * math.pi * k / 32 for k in range(32))]
        tower = mesh_mod.box(380.0, 380.0, 0.0, 250.0, cx=tx, cy=ty)
        for k in range(DSF_TOWER_TIERS):
            side = 300.0 - 14.0 * k
            tower = tower.merged(mesh_mod.box(side, side, 250.0 + 50.0 * k, 300.0 + 50.0 * k, cx=tx, cy=ty))
        tower = tower.merged(mesh_mod.box(60.0, 60.0, 900.0, 960.0, cx=tx, cy=ty))   # 顶部铜蒺藜（示意）
        parts.append((f"{name}/marble", tower.merged(polygon_ring(basin, 40.0, POOL_FLOOR_CM, POOL_CURB_CM))))
        parts.append((f"{name}/water", terrain_mod.polygon_slab(basin, z_top=POOL_WATER_CM, depth=5.0)))
        for k in range(DSF_TOWER_JETS):                                          # 池底八喷管，水射高六尺
            a = 2 * math.pi * k / DSF_TOWER_JETS
            px, py = tx + 300.0 * math.cos(a), ty + 300.0 * math.sin(a)
            parts.append((f"{name}_pipe_{k + 1}/jet", jet((px, py, POOL_WATER_CM), (px, py, 190.0))))
        parts.append((f"{name}_top/jet", jet((tx, ty, 960.0), (tx, ty, 1150.0))))   # 塔顶铜蒺藜喷水
    return parts


def build_guanshuifa() -> list[Part]:
    """观水法（坐南朝北）：平台与两侧石阶、弧形五扇石屏、宝座与台阶、铜鹤、方塔、鼎炉、东西巴洛克门。"""
    parts: list[Part] = []
    zp = GSF_PLATFORM_H_CM
    y_front, y_back = GSF_Y + 300.0, GSF_Y - 300.0
    plat = mesh_mod.box(2 * GSF_HALF_CM, y_front - y_back, 0.0, zp, cy=GSF_Y)
    for s in (-1.0, 1.0):                                         # 两侧石阶北下
        plat = plat.merged(flight(s * 650.0, y_front, s * 650.0, y_front + 300.0, 300.0, zp, 0.0, 8))
    for k, r in enumerate((260.0, 210.0, 160.0)):                 # 宝座前弧形台阶
        plat = plat.merged(_half_disc(GSF_Y - 50.0, r, zp, zp + 45.0 * (k + 1), sign=1.0))
    # 弧形石屏（凹面朝北）：五扇沿圆弧
    chord, sag = GSF_SCREEN_CHORD_CM, GSF_SCREEN_SAG_CM
    radius = (chord ** 2 / 4.0 + sag ** 2) / (2.0 * sag)
    cy = (GSF_Y - 150.0) + radius                                 # 圆心在屏北
    half_ang = math.asin(chord / 2.0 / radius)
    screen = mesh_mod.Mesh()
    for k in range(GSF_SCREEN_PANELS):
        a0 = -math.pi / 2 - half_ang + 2 * half_ang * k / GSF_SCREEN_PANELS
        a1 = -math.pi / 2 - half_ang + 2 * half_ang * (k + 1) / GSF_SCREEN_PANELS
        p0 = (radius * math.cos(a0), cy + radius * math.sin(a0))
        p1 = (radius * math.cos(a1), cy + radius * math.sin(a1))
        screen = screen.merged(obox(p0[0], p0[1], p1[0], p1[1], 50.0, zp, zp + GSF_SCREEN_H_CM))
        screen = screen.merged(obox(p0[0], p0[1], p1[0], p1[1], 70.0, zp + GSF_SCREEN_H_CM,
                                    zp + GSF_SCREEN_H_CM + 40.0))
    # 方塔（石屏东西）、鼎炉（台前）
    for s in (-1.0, 1.0):
        screen = screen.merged(mesh_mod.box(100.0, 100.0, zp, zp + 60.0, cx=s * 520.0, cy=GSF_Y - 150.0))
        screen = screen.merged(hip_roof_xy(s * 520.0, GSF_Y - 150.0, 80.0, 81.0, zp + 60.0, 230.0))
        screen = screen.merged(mesh_mod.box(120.0, 120.0, 0.0, 160.0, cx=s * 420.0, cy=y_front + 60.0))
        screen = screen.merged(mesh_mod.cylinder(160.0, 230.0, 50.0, s * 420.0, y_front + 60.0, 12))
    # 东西巴洛克角门与花墙
    for s in (-1.0, 1.0):
        screen = screen.merged(mesh_mod.box(300.0, 80.0, 0.0, 320.0, cx=s * (GSF_HALF_CM + 150.0), cy=GSF_Y))
        wall_x0 = GSF_HALF_CM + 300.0                               # 角门外侧至广场边的花墙
        screen = screen.merged(mesh_mod.box(PLAZA_HALF_CM - wall_x0, 40.0, 0.0, 250.0,
                                            cx=s * (wall_x0 + PLAZA_HALF_CM) / 2.0, cy=GSF_Y))
    parts.append(("guanshuifa/marble", plat.merged(screen)))
    doors = mesh_mod.Mesh()
    for s in (-1.0, 1.0):
        doors = doors.merged(_panel_y(GSF_Y + 40.0, s * (GSF_HALF_CM + 150.0), 160.0, 0.0, 240.0, 1.0))
    parts.append(("guanshuifa/windows", doors))
    throne = mesh_mod.box(140.0, 90.0, zp + 135.0, zp + 230.0, cy=GSF_Y - 50.0)
    throne = throne.merged(mesh_mod.box(140.0, 20.0, zp + 230.0, zp + 330.0, cy=GSF_Y - 95.0))
    for s in (-1.0, 1.0):                                         # 铜鹤一对（衔横条撑凉棚）
        throne = throne.merged(mesh_mod.box(40.0, 60.0, zp, zp + 260.0, cx=s * 170.0, cy=GSF_Y + 60.0))
    parts.append(("guanshuifa_throne/bronze", throne))
    return parts


def build_yuanyingguan_dashuifa_scene() -> list[Part]:
    """远瀛观·大水法·观水法景：北高台楼阁、中石龛喷泉、南观水台，之间为广场铺地与两株线法松。"""
    pave = mesh_mod.box(2 * PLAZA_HALF_CM, (GSF_Y + 300.0) - (-1300.0), -5.0, 0.0,
                        cy=((GSF_Y + 300.0) + (-1300.0)) / 2.0)
    crowns, trunks = mesh_mod.Mesh(), mesh_mod.Mesh()
    for s in (-1.0, 1.0):                         # 线法松（维基「三层线法松」、铜版画十五：多层盘状）
        c, t = topiary(s * 600.0, -1600.0, tiers=7, height=900.0, radius=150.0)
        crowns, trunks = crowns.merged(c), trunks.merged(t)
    return (build_yuanyingguan() + build_dashuifa() + build_guanshuifa()
            + [("plaza/paving", pave), ("pines/foliage", crowns), ("pines/bark", trunks)])
