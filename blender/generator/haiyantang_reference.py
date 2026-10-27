"""haiyantang_reference.py — 海晏堂「参考图效果版」（**非史料复原**，见 ADR-0003）。

按用户提供的参考效果图（AI 生成的写实海晏堂图像）布置，而非按史料：
- 立面、雕饰一律米白石材（史料为粉红色灰墙 + 汉白玉，S-023）；屋面灰瓦（史料为孔雀绿琉璃）；
- 楼前大椭圆水池（史料为「菱形」池），十二生肖为全铜袍服坐像，立于池沿内的雕花石座上，
  南北各六、面向池心喷水（史料为八字墙两列）；
- 池心假山群像喷泉、池前缘贝壳卷涡雕饰、瓶饰；檐上瓶饰、门罩两侧立像、券窗上花环；
- 广场四周阔叶乔木与柏树。

正楼、石跑梯、导水台、蓄水楼、楼南北喷水池沿用 western.py 的史料版几何，只改材质类：
``walls`` → ``limestone``，``glazed_roof`` / ``glazed_ridge`` → ``roof``，琉璃番花 → ``limestone``。

局部坐标与 western.py 相同（+X 东、+Y 北，原点 = 蓄水楼中心）；
网格标签末段为材质类，中文名在 web/app/src/labels.ts。
"""

from __future__ import annotations

import math
import random

from generator import mesh as mesh_mod
from generator import sculpt
from generator import terrain as terrain_mod
from generator import western as w
from generator.western import Part

# 楼前椭圆池（参考图：池宽几占两跑石梯之间；尺寸按现有石梯位置取，参考图无尺度）
POOL_CX = -7000.0
POOL_RX, POOL_RY = 1650.0, 1250.0       # 东西（朝观者纵深）、南北半轴：参考图池身前后长、两侧平直
POOL_SHAPE_N = 4.0                       # 超椭圆指数：4 = 圆角长方形（两侧长边平直，铜像沿边成列）
POOL_SEGMENTS = 64
RIM_T_CM, RIM_H_CM = 55.0, 55.0          # 池沿厚、高出地坪
POOL_FLOOR_CM, POOL_WATER_CM = -80.0, 15.0

ROW_EAST, ROW_WEST = 0.62, -0.7          # 两列铜像东、西端位置（占池东西半轴）
ROW_INSET_CM = 170.0                     # 石座中心距池长边的内收
ROW_FACE_FORWARD = 0.3                   # 铜像朝向略偏向池前（西，观者一侧）
PEDESTAL_TOP_CM = 130.0                  # 雕花石座顶（高出水面约 1.15 m，参考图）
HEAD_SCALE = 1.4                         # 兽首相对身躯放大（现存铜首连颈高约 40–50 cm，比例偏大）
FIGURE_HEIGHT_CM = 190.0                 # 单图生成铜像（连圆底座）通高：参考图中铜像约为人高 1.3 倍
STANDING_HEAD_SCALE = 1.8               # 参考图立像兽首约占通高四分之一
FIGURE_SCALE = 1.4                       # 立像连首约高 2.6 m（参考图：铜像明显高过人）

ROCK_R_CM = 330.0                        # 池心假山群
CENTRE_JET_CM = 950.0                    # 中央主喷高
RING_JETS, RING_R_CM, RING_JET_CM = 8, 380.0, 520.0

COURT_X0, COURT_X1 = -10500.0, w.MAIN_WEST_X - w.FRONT_PROJ_CM - w.LANDING_DEPTH_CM
COURT_HALF_CM = 3300.0

# 人视（参考图机位）：池前缘外、人眼高，望向门罩二层
EYE = (POOL_CX - POOL_RX - 1300.0, 0.0, 170.0)
EYE_TARGET = (w.MAIN_WEST_X, 0.0, 900.0)

LIMESTONE_REMAP = {"walls": "limestone", "marble": "limestone", "glazed_roof": "roof", "glazed_ridge": "roof"}


def _remap(parts: list[Part]) -> list[Part]:
    """史料版构件改材质类：粉红灰墙 → 米白石、琉璃瓦 → 灰瓦、琉璃番花 → 石雕。"""
    out: list[Part] = []
    for label, m in parts:
        head, _, cls = label.rpartition("/")
        if "medallions" in head:
            cls = "limestone"
        else:
            cls = LIMESTONE_REMAP.get(cls, cls)
        out.append((f"{head}/{cls}" if head else cls, m))
    return out


def _se(t: float, rx: float, ry: float) -> tuple[float, float]:
    """超椭圆（圆角长方形）上参数 t 处的点（相对池心）。"""
    c, s = math.cos(t), math.sin(t)
    e = 2.0 / POOL_SHAPE_N
    return (rx * math.copysign(abs(c) ** e, c), ry * math.copysign(abs(s) ** e, s))


def _ellipse(rx: float, ry: float, n: int = POOL_SEGMENTS, cx: float = POOL_CX) -> list[tuple[float, float]]:
    """池轮廓（圆角长方形，逆时针）。"""
    return [(cx + _se(2 * math.pi * k / n, rx, ry)[0], _se(2 * math.pi * k / n, rx, ry)[1]) for k in range(n)]


def blob(cx: float, cy: float, cz: float, r: float, rng: random.Random, seg: int = 9, rings: int = 6,
         jitter: float = 0.18, squash: float = 1.0) -> mesh_mod.Mesh:
    """不规则团块（树冠簇、假山石）：经纬球顶点沿径向随机起伏。"""
    verts: list[tuple[float, float, float]] = [(cx, cy, cz - r * squash)]
    for i in range(1, rings):
        phi = math.pi * i / rings - math.pi / 2.0
        for k in range(seg):
            th = 2 * math.pi * (k + 0.5 * (i % 2)) / seg
            rr = r * (1.0 + jitter * (rng.random() * 2.0 - 1.0))
            verts.append((cx + rr * math.cos(phi) * math.cos(th), cy + rr * math.cos(phi) * math.sin(th),
                          cz + rr * math.sin(phi) * squash))
    verts.append((cx, cy, cz + r * squash))
    faces: list[tuple[int, ...]] = []
    top = len(verts) - 1
    for k in range(seg):
        k2 = (k + 1) % seg
        faces.append((0, 1 + k2, 1 + k))
        faces.append((top, 1 + (rings - 2) * seg + k, 1 + (rings - 2) * seg + k2))
    for i in range(rings - 2):
        a, b = 1 + i * seg, 1 + (i + 1) * seg
        for k in range(seg):
            k2 = (k + 1) % seg
            faces.append((a + k, a + k2, b + k2, b + k))
    return mesh_mod.Mesh(vertices=verts, faces=faces)


def _spiral(cx: float, z0: float, x_plane: float, r0: float, turns: float, sign: float, n: int = 18
            ) -> list[tuple[float, float, float]]:
    """立面上的卷涡（对数螺线）点列：自外缘 r0 内卷 ``turns`` 圈，sign 决定左右卷向。"""
    pts = []
    for k in range(n + 1):
        t = turns * 2 * math.pi * k / n
        r = r0 * math.exp(-0.32 * t)
        pts.append((x_plane, cx + sign * r * math.cos(t), z0 + r * math.sin(t)))
    return pts


def _chain(pts: list[tuple[float, float, float]], width: float) -> mesh_mod.Mesh:
    out = mesh_mod.Mesh()
    for a, b in zip(pts, pts[1:]):
        out = out.merged(w.beam(a, b, width))
    return out


# 兽首造型（参考图式全铜像；吻长、吻宽、耳 / 角类型，单位 cm @ scale 1）
ANIMAL_HEADS = {
    "rat": (16, 9, "round"), "ox": (14, 14, "ox"), "tiger": (12, 13, "small"), "rabbit": (10, 10, "long"),
    "dragon": (20, 12, "dragon"), "snake": (16, 8, None), "horse": (22, 10, "pointed"), "goat": (16, 9, "goat"),
    "monkey": (7, 11, "round"), "rooster": (9, 5, "comb"), "dog": (15, 10, "pointed"), "pig": (10, 13, "floppy"),
}
# 耳 / 角：头部局部 (前, 侧, 高) 点列，侧向取正值后左右镜像；末项为粗细
_EARS = {
    "round": ([(-2, 9, 26), (-3, 13, 33)], 9), "small": ([(-1, 9, 27), (-2, 11, 32)], 6),
    "pointed": ([(-1, 7, 25), (-2, 9, 38)], 6), "long": ([(-2, 5, 26), (-5, 7, 48)], 6),
    "floppy": ([(0, 10, 24), (5, 15, 18)], 8), "ox": ([(-2, 10, 26), (-2, 18, 30), (1, 21, 38)], 5),
    "goat": ([(-2, 6, 28), (-8, 9, 32), (-11, 11, 26), (-8, 12, 20)], 5),
    "dragon": ([(-2, 6, 28), (-8, 9, 40), (-14, 10, 46)], 4),
}


def robed_figure(x: float, y: float, z: float, face: tuple[float, float], scale: float,
                 animal: str | None) -> tuple[mesh_mod.Mesh, mesh_mod.Mesh, tuple[float, float, float]]:
    """袍服坐像（生肖像 / 假山与立面上的石像）：垂褶袍身、膝、广袖、交领 + 头。

    ``animal`` 为生肖英文名时作铜铸兽首（sculpt.animal_head），否则为人首束髻。
    ``face`` 为朝向（平面单位向量）；返回 (身躯, 头, 口部位置)。尺寸单位 cm @ scale 1。
    """
    fx, fy = face
    px, py = -fy, fx                                              # 侧向
    s = scale

    def P(a: float, b: float, h: float) -> tuple[float, float, float]:
        return (x + (fx * a + px * b) * s, y + (fy * a + py * b) * s, z + h * s)

    out = sculpt.robed_body(x, y, z, face, s)
    hz = 100.0
    if animal is None:
        head = w.lathe(w._scaled([(6, 0), (11, 4), (14, 12), (14, 20), (11, 27), (5, 31), (1, 33)], s, s),
                       x, y, z + hz * s, seg=12)
        head = head.merged(w.lathe(w._scaled([(6, 0), (8, 4), (5, 9), (1, 11)], s, s), *P(-3, 0, hz + 30)[:2],
                                   z + (hz + 30) * s, seg=8))   # 束髻
        return out, head, P(15, 0, hz + 12)
    m, mouth = sculpt.animal_head(animal)                         # 铜铸兽首（雕塑式，sculpt.py）
    hs = s * HEAD_SCALE
    head_z = z + (hz - 4) * s
    return out, sculpt.place(m, x, y, head_z, face, hs), sculpt.place_point(mouth, x, y, head_z, face, hs)


def _curl(centre: tuple[float, float], r0: float, turns: float, out_dir: tuple[float, float], start_deg: float,
          n: int = 14) -> list[tuple[float, float, float]]:
    """竖直面内的涡卷（对数螺线）：centre = (沿 out_dir 的水平距离, 高)，返回局部 (a, b, h) 点列。"""
    da, db = out_dir
    pts = []
    for k in range(n + 1):
        t = math.radians(start_deg) + turns * 2 * math.pi * k / n
        r = r0 * math.exp(-0.28 * turns * 2 * math.pi * k / n)
        u, h = centre[0] + r * math.cos(t), centre[1] + r * math.sin(t)
        pts.append((da * u, db * u, h))
    return pts


def carved_pedestal(x: float, y: float, z0: float, z1: float, face: tuple[float, float]) -> mesh_mod.Mesh:
    """方形雕花石座（参考图）：座、束身、四角 S 形涡卷托、四面椭圆花框与叶饰、檐口与顶板。"""
    h = z1 - z0
    loc = mesh_mod.box(130.0, 130.0, 0.0, h * 0.2)                                  # 座
    loc = loc.merged(mesh_mod.box(96.0, 96.0, h * 0.2, h * 0.8))                    # 束身
    loc = loc.merged(mesh_mod.box(124.0, 124.0, h * 0.8, h * 0.87))                 # 檐口
    loc = loc.merged(mesh_mod.box(112.0, 112.0, h * 0.87, h))                       # 顶板
    for sa in (-1.0, 1.0):                                         # 四角 S 形涡卷：上小卷、外鼓、下大卷
        for sb in (-1.0, 1.0):
            d = (sa / math.sqrt(2), sb / math.sqrt(2))
            top = _curl((58.0, h * 0.74), 13.0, 1.1, d, 90.0)
            mid = [(d[0] * u, d[1] * u, hh) for u, hh in ((70.0, h * 0.66), (74.0, h * 0.52), (70.0, h * 0.4))]
            bottom = _curl((60.0, h * 0.3), 16.0, 1.2, d, 0.0)
            path = top[::-1] + mid + bottom
            loc = loc.merged(sculpt.tube(path, [7.0] * len(path), sides=8))
    for k in range(4):                                             # 四面：椭圆花框 + 三片叶饰 + 下垂花穗
        ang = math.pi / 2 * k
        ca, sa_ = math.cos(ang), math.sin(ang)
        side = (-sa_, ca)

        def P(u: float, v: float, hh: float) -> tuple[float, float, float]:
            return (ca * u + side[0] * v, sa_ * u + side[1] * v, hh)

        ring = [P(50.0, 22.0 * math.cos(t), h * 0.55 + 28.0 * math.sin(t))
                for t in (2 * math.pi * q / 16 for q in range(17))]
        loc = loc.merged(sculpt.tube(ring, [5.0] * len(ring), sides=6))
        loc = loc.merged(sculpt.ellipsoid(P(49.0, 0.0, h * 0.55), (3.0, 16.0, 21.0), seg=12, rings=8).mesh())
        for v in (-24.0, 0.0, 24.0):
            loc = loc.merged(sculpt.tube([P(50.0, v * 0.3, h * 0.24), P(54.0, v, h * 0.33), P(51.0, v * 1.3, h * 0.38)],
                                         [6.0, 5.0, 1.5], flat=0.4, sides=6, up=(ca, sa_, 0.0)))
        loc = loc.merged(sculpt.tube([P(50.0, 0.0, h * 0.82), P(53.0, 0.0, h * 0.74), P(51.0, 0.0, h * 0.68)],
                                     [6.0, 5.0, 2.0], sides=6))
    return sculpt.place(loc, x, y, z0, face, 1.0)


def _pedestal(x: float, y: float, z0: float, z1: float) -> mesh_mod.Mesh:
    """雕花石座：八棱，座、束腰、卷边托盘（参考图中带卷涡雕饰的方座，此为旋转体近似）。"""
    h = z1 - z0
    prof = [(62, 0), (62, 0.12), (52, 0.2), (44, 0.26), (40, 0.6), (46, 0.68), (58, 0.8), (64, 0.9), (64, 1.0)]
    return w.lathe([(r, t * h) for r, t in prof], x, y, z0, seg=8, phase_deg=22.5)


def build_reference_pool() -> list[Part]:
    """椭圆生肖池：池壁池沿、水面、十二铜像石座与喷水、池心假山喷泉、前缘贝壳卷涡与瓶饰、广场铺地。"""
    parts: list[Part] = []
    rim_pts = _ellipse(POOL_RX, POOL_RY)
    rim = w.polygon_ring(rim_pts, RIM_T_CM, POOL_FLOOR_CM, RIM_H_CM)
    rim = rim.merged(w.polygon_ring(_ellipse(POOL_RX + 18.0, POOL_RY + 18.0), 30.0, RIM_H_CM, RIM_H_CM + 10.0))  # 池沿压面
    inner = _ellipse(POOL_RX - RIM_T_CM / 2.0, POOL_RY - RIM_T_CM / 2.0)
    rim = rim.merged(terrain_mod.polygon_slab(inner, z_top=POOL_FLOOR_CM, depth=10.0))
    # 前缘（西半）石栏杆与瓶饰：贝壳雕饰处留口
    rail = mesh_mod.Mesh()
    ring_out = _ellipse(POOL_RX + 40.0, POOL_RY + 40.0, 48)
    for k in range(48):
        ang = 360.0 * k / 48
        if not 118.0 <= ang <= 242.0 or 160.0 < ang < 200.0:
            continue
        (xa, ya), (xb, yb) = ring_out[k], ring_out[(k + 1) % 48]
        rail = rail.merged(w.balustrade(xa, ya, xb, yb, RIM_H_CM + 10.0, 85.0))
    for ang in (118.0, 160.0, 200.0, 242.0):                     # 栏杆端墩上的大瓶饰
        px, y = _se(math.radians(ang), POOL_RX + 40.0, POOL_RY + 40.0)
        x = POOL_CX + px
        rail = rail.merged(mesh_mod.box(90.0, 90.0, RIM_H_CM, RIM_H_CM + 120.0, cx=x, cy=y))
        rail = rail.merged(w.urn(x, y, RIM_H_CM + 120.0, 2.0))
    parts.append(("zodiac_pool/limestone", rim.merged(rail)))
    parts.append(("zodiac_pool/water", terrain_mod.polygon_slab(inner, z_top=POOL_WATER_CM, depth=5.0)))

    named = sculpt.load_figure_named()                  # 各生肖专属铜像（<生肖>.obj），缺的用其余造型轮换
    figures = list(named.values())
    fig_index = 0
    # 十二生肖：参考图式整体铸造的铜坐像，沿池两侧长边各列六尊，面向池中线（北侧 牛兔蛇羊鸡猪、南侧 鼠虎龙马猴狗）
    for names, s in ((w.ZODIAC_NORTH, 1.0), (w.ZODIAC_SOUTH, -1.0)):
        for k, name in enumerate(names):
            x = POOL_CX + POOL_RX * (ROW_EAST - (ROW_EAST - ROW_WEST) * k / (len(names) - 1))
            y = s * (POOL_RY - ROW_INSET_CM)
            fl = math.hypot(ROW_FACE_FORWARD, 1.0)
            face = (-ROW_FACE_FORWARD / fl, -s / fl)                # 面向池中线，略朝前（观者）
            ped = carved_pedestal(x, y, POOL_FLOOR_CM, PEDESTAL_TOP_CM, face)
            if figures:                                          # 参考图铜像：单图生成 3D 的整尊模型（一体）
                if name in named:
                    m, mouth_local = named[name]
                else:
                    m, mouth_local = figures[fig_index % len(figures)]
                    fig_index += 1
                bronze = sculpt.place(m, x, y, PEDESTAL_TOP_CM, face, FIGURE_HEIGHT_CM)
                mouth = sculpt.place_point(mouth_local, x, y, PEDESTAL_TOP_CM, face, FIGURE_HEIGHT_CM)
            else:                                                # 无模型时退回雕塑立像
                body = sculpt.standing_robe(x, y, PEDESTAL_TOP_CM, face, FIGURE_SCALE)
                m, mouth_local = sculpt.animal_head(name)
                head_z = PEDESTAL_TOP_CM + (sculpt.STANDING_HEIGHT - 5.0) * FIGURE_SCALE
                hs = FIGURE_SCALE * STANDING_HEAD_SCALE
                mouth = sculpt.place_point(mouth_local, x, y, head_z, face, hs)
                bronze = body.merged(sculpt.place(m, x, y, head_z, face, hs))
            parts.append((f"zodiac_{name}/limestone", ped))
            parts.append((f"zodiac_{name}/bronze", bronze))
            land = (x + face[0] * 450.0, y + face[1] * 450.0, POOL_WATER_CM)
            parts.append((f"zodiac_{name}/jet", w.jet(mouth, land)))

    # 池心假山群像喷泉：不规则石团堆叠 + 两尊石像，中央主喷 + 一圈八道
    rng = random.Random(7)
    rock = mesh_mod.Mesh()
    for k in range(9):
        a = 2 * math.pi * k / 9 + rng.random() * 0.4
        rr = ROCK_R_CM * (0.35 + 0.45 * rng.random())
        rock = rock.merged(blob(POOL_CX + rr * math.cos(a), rr * math.sin(a), 20.0 + rng.random() * 40.0,
                                90.0 + rng.random() * 70.0, rng, seg=12, rings=8, jitter=0.18, squash=0.7))
    rock = rock.merged(blob(POOL_CX, 0.0, 140.0, 150.0, rng, seg=14, rings=9, jitter=0.15, squash=0.8))
    rock = rock.merged(blob(POOL_CX, 0.0, 260.0, 80.0, rng, seg=12, rings=8, jitter=0.15))
    for sx in (-1.0, 1.0):
        body, head, _ = robed_figure(POOL_CX + 60.0, sx * 120.0, 180.0, (-1.0, 0.0), 1.1, animal=None)
        rock = rock.merged(body).merged(head)
    rock = rock.merged(w.lathe([(28, 0), (40, 20), (18, 45), (12, 80), (30, 95), (8, 110)], POOL_CX, 0.0, 330.0, seg=10))
    parts.append(("rock_fountain/limestone", rock))
    parts.append(("rock_fountain/centre/jet", w.jet((POOL_CX, 0.0, 440.0), (POOL_CX, 0.0, CENTRE_JET_CM))))
    for k in range(RING_JETS):
        a = 2 * math.pi * (k + 0.5) / RING_JETS
        x, y = POOL_CX + RING_R_CM * math.cos(a), RING_R_CM * math.sin(a)
        parts.append((f"rock_fountain/ring_{k + 1}/jet", w.jet((x, y, POOL_WATER_CM), (x, y, RING_JET_CM))))

    parts.append(("shell_cartouche/limestone", _shell_cartouche()))
    parts.append(("court/paving", _court_paving()))
    return parts


def _shell_cartouche() -> mesh_mod.Mesh:
    """池前缘正中贝壳卷涡雕饰（参考图前景）：九瓣扇贝 + 两侧 C 形卷涡与叶饰，背靠池沿。"""
    x0 = POOL_CX - POOL_RX - 60.0
    base = RIM_H_CM + 10.0
    out = mesh_mod.box(70.0, 760.0, 0.0, base + 40.0, cx=x0)
    fan = []
    for k in range(37):
        t = math.pi * k / 36
        r = 190.0 * (1.0 + 0.08 * math.cos(9 * t))
        fan.append((r * math.cos(t), base + 40.0 + r * math.sin(t)))
    out = out.merged(w.extrude_vertical(fan, "x", x0 - 20.0, x0 + 20.0))
    for k in range(1, 9):                                         # 扇贝放射肋
        t = math.pi * k / 9
        out = out.merged(w.beam((x0 - 26.0, 0.0, base + 50.0),
                                (x0 - 26.0, 175.0 * math.cos(t), base + 40.0 + 175.0 * math.sin(t)), 14.0))
    for s in (-1.0, 1.0):                                         # 两侧卷涡：大 C 卷 + 外卷小涡 + 叶饰
        out = out.merged(_chain(_spiral(s * 300.0, base + 110.0, x0 - 18.0, 120.0, 1.3, s), 26.0))
        out = out.merged(_chain(_spiral(s * 520.0, base + 60.0, x0 - 14.0, 70.0, 1.1, -s), 20.0))
        for k in range(5):
            yy = s * (200.0 + 70.0 * k)
            out = out.merged(w.beam((x0 - 10.0, yy, base + 30.0), (x0 - 40.0, yy + s * 40.0, base + 90.0 + 15.0 * (k % 2)), 18.0))
    return out


def _court_paving() -> mesh_mod.Mesh:
    """广场铺地：椭圆池外缘到矩形广场边界的放射分块（只有顶面；跨角的块含角点）。"""
    rx, ry = POOL_RX + RIM_T_CM / 2.0, POOL_RY + RIM_T_CM / 2.0
    n = 96

    def ray(t: float) -> tuple[tuple[float, float], str]:
        dx, dy = _se(t, rx, ry)
        tx = ((COURT_X1 - POOL_CX) / dx) if dx > 1e-9 else ((COURT_X0 - POOL_CX) / dx) if dx < -1e-9 else math.inf
        ty = (COURT_HALF_CM / abs(dy)) if abs(dy) > 1e-9 else math.inf
        if tx < ty:
            return (POOL_CX + dx * tx, dy * tx), "x+" if dx > 0 else "x-"
        return (POOL_CX + dx * ty, dy * ty), "y+" if dy > 0 else "y-"

    corners = {("x+", "y+"): (COURT_X1, COURT_HALF_CM), ("y+", "x-"): (COURT_X0, COURT_HALF_CM),
               ("x-", "y-"): (COURT_X0, -COURT_HALF_CM), ("y-", "x+"): (COURT_X1, -COURT_HALF_CM)}
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    for k in range(n):
        t0, t1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        e0 = (POOL_CX + _se(t0, rx, ry)[0], _se(t0, rx, ry)[1])
        e1 = (POOL_CX + _se(t1, rx, ry)[0], _se(t1, rx, ry)[1])
        (r0, s0), (r1, s1) = ray(t0), ray(t1)
        poly = [e0, r0] + ([corners[(s0, s1)]] if s0 != s1 else []) + [r1, e1]
        base = len(verts)
        verts += [(x, y, 0.0) for x, y in poly]
        faces.append(tuple(range(base, base + len(poly))))
    return mesh_mod.Mesh(vertices=verts, faces=faces)


def facade_ornament() -> list[Part]:
    """正楼加饰：檐上露顶栏杆瓶饰、门罩两侧二层立像、上层券窗上花环与小涡卷。"""
    edges = [-w.MAIN_LEN_CM / 2.0]
    for seg in w.MAIN_SEGMENTS_CM:
        edges.append(edges[-1] + seg)
    orn = mesh_mod.Mesh()
    for x in (w.MAIN_WEST_X + 10.0, w.MAIN_EAST_X - 10.0):          # 檐上瓶饰（每壁柱一只）
        y = edges[1]
        while y <= edges[4] + 1.0:
            orn = orn.merged(mesh_mod.box(50.0, 50.0, w.MAIN_EAVE_CM, w.MAIN_EAVE_CM + 95.0, cx=x, cy=y))
            orn = orn.merged(w.urn(x, y, w.MAIN_EAVE_CM + 95.0, 1.5))
            y += w.MAIN_SEGMENTS_CM[1] / 2.0
    x_col = w.MAIN_WEST_X - w.FRONT_PROJ_CM - w.SKIN_CM - 45.0
    statues = mesh_mod.Mesh()
    for y in (-430.0, 430.0):                                     # 门罩两侧立像（参考图二层壁龛立像）
        statues = statues.merged(mesh_mod.box(80.0, 80.0, w.FLOOR2_CM + 30.0, w.FLOOR2_CM + 120.0, cx=x_col, cy=y))
        body, head, _ = robed_figure(x_col, y, w.FLOOR2_CM + 120.0, (-1.0, 0.0), 1.7, animal=None)
        statues = statues.merged(body).merged(head)
    for i, (seg, bays) in enumerate(zip(w.MAIN_SEGMENTS_CM, w.MAIN_SEGMENT_BAYS)):
        proj = w.PAVILION_PROJ_CM if i in (0, 4) else w.FRONT_PROJ_CM if i == 2 else 0.0
        xf = w.MAIN_WEST_X - proj - w.SKIN_CM - 8.0
        bw = seg / bays
        for k in range(bays):
            uc = edges[i] + bw * (k + 0.5)
            half = bw * 0.3
            swag = [(xf, uc - half + 2 * half * q / 8, 1335.0 - 40.0 * math.sin(math.pi * q / 8)) for q in range(9)]
            orn = orn.merged(_chain(swag, 16.0))                  # 花环
            orn = orn.merged(w.lathe([(14, 0), (20, 14), (14, 30), (4, 38)], xf - 6.0, uc, 1335.0, seg=8))
            for s in (-1.0, 1.0):
                orn = orn.merged(_chain(_spiral(uc + s * (half + 10.0), 1330.0, xf, 30.0, 1.0, s, 10), 10.0))
    return [("front_building/ornament/limestone", orn), ("front_building/statues/limestone", statues)]


def leaf_cards(points: list[tuple[float, float, float]], size: float, rng: random.Random) -> mesh_mod.Mesh:
    """叶片卡（游戏常用做法）：每点一张随机朝向的方形面片，查看器贴透明叶簇纹理。"""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    h = size / 2.0
    for cx, cy, cz in points:
        z = rng.random() * 2.0 - 1.0                              # 随机单位法向
        a = rng.random() * 2 * math.pi
        n = (math.sqrt(1 - z * z) * math.cos(a), math.sqrt(1 - z * z) * math.sin(a), z)
        ref = (0.0, 0.0, 1.0) if abs(n[2]) < 0.9 else (1.0, 0.0, 0.0)
        u = (n[1] * ref[2] - n[2] * ref[1], n[2] * ref[0] - n[0] * ref[2], n[0] * ref[1] - n[1] * ref[0])
        ul = math.sqrt(sum(c * c for c in u))
        u = tuple(c / ul * h for c in u)
        v = (n[1] * u[2] - n[2] * u[1], n[2] * u[0] - n[0] * u[2], n[0] * u[1] - n[1] * u[0])
        base = len(verts)
        for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            verts.append((cx + su * u[0] + sv * v[0], cy + su * u[1] + sv * v[1], cz + su * u[2] + sv * v[2]))
        faces.append((base, base + 1, base + 2, base + 3))
    return mesh_mod.Mesh(vertices=verts, faces=faces)


def _ellipsoid_points(cx: float, cy: float, cz: float, r: float, rz: float, n: int, rng: random.Random
                      ) -> list[tuple[float, float, float]]:
    """椭球壳层内的随机点（叶片卡中心：偏外层，树冠轮廓饱满、内部稀）。"""
    pts = []
    while len(pts) < n:
        x, y, z = (rng.random() * 2 - 1 for _ in range(3))
        d = x * x + y * y + z * z
        if 0.3 < d <= 1.0:
            pts.append((cx + x * r, cy + y * r, cz + z * rz))
    return pts


def stair_arcades() -> list[Part]:
    """石梯西面的券廊（参考图：门前平台下三开间券洞，两跑石梯下逐级降低的盲券），代替整面实墙。

    券面为 35 cm 墙皮开洞（western.opening_bay），洞内为暗色退进面（``recess``）。
    """
    face = COURT_X1                                                # 门前平台与上跑石梯的西面
    skin, recess, trim = mesh_mod.Mesh(), mesh_mod.Mesh(), mesh_mod.Mesh()

    def bay(u0: float, u1: float, z1: float, width: float, head: float) -> None:
        nonlocal skin, recess, trim
        uc = (u0 + u1) / 2.0
        sk, gl, mb = w.opening_bay("x", face, -1.0, u0, u1, 0.0, z1, uc - width / 2, uc + width / 2, 0.0, head, True)
        skin, recess, trim = skin.merged(sk), recess.merged(gl), trim.merged(mb)

    half = w.LANDING_HALF_CM
    for k in range(3):                                             # 平台下三开间
        u0 = -half + 2 * half * k / 3
        bay(u0, u0 + 2 * half / 3, w.FLOOR2_CM - 40.0, 250.0, 470.0)
    run = w.UPPER_RUN_END_CM - half
    for s in (-1.0, 1.0):                                          # 上跑下盲券：随踏步降低
        for k in range(2):
            ya, yb = half + run * k / 2, half + run * (k + 1) / 2
            z_outer = w.FLOOR2_CM - (w.FLOOR2_CM - w.MID_LANDING_Z_CM) * (yb - half) / run
            z1 = z_outer - 40.0
            r = 120.0
            if z1 - r - 25.0 < 150.0:
                continue
            u0, u1 = sorted((s * ya, s * yb))
            bay(u0, u1, z1, 2 * r, z1 - r - 25.0)
    return [("west_stairs/arcade/limestone", skin.merged(trim)), ("west_stairs/arcade/recess", recess)]


def build_trees() -> list[Part]:
    """广场两侧与楼侧的阔叶乔木、柏树（参考图背景；株数位置为布景）：叶片卡树冠 + 树干枝杈。"""
    rng = random.Random(11)
    parts: list[Part] = []
    bark = mesh_mod.Mesh()

    def broadleaf(x: float, y: float, h: float) -> None:
        nonlocal bark
        r = h * 0.3
        zc = h * 0.62
        bark = bark.merged(w.lathe([(h * 0.045, 0), (h * 0.032, h * 0.4), (h * 0.02, h * 0.55)], x, y, 0.0, seg=7))
        pts: list[tuple[float, float, float]] = []
        for _ in range(5):                                        # 树冠 = 主团 + 若干副团（轮廓起伏）
            a = rng.random() * 2 * math.pi
            d = r * 0.45 * rng.random()
            bx, by, bz = x + d * math.cos(a), y + d * math.sin(a), zc + (rng.random() - 0.3) * r * 0.5
            pts += _ellipsoid_points(bx, by, bz, r * 0.7, r * 0.55, 34, rng)
            bark = bark.merged(w.beam((x, y, h * 0.4), (bx, by, bz - r * 0.2), h * 0.022))   # 枝杈
        parts.append((f"tree_{len(parts) + 1}/leaves", leaf_cards(pts, h * 0.13, rng)))

    def spire(x: float, y: float, h: float) -> None:
        nonlocal bark
        r = h * 0.12
        bark = bark.merged(mesh_mod.cylinder(0.0, h * 0.15, r * 0.2, x, y, 6))
        pts = []
        for k in range(70):
            t = rng.random()
            z = h * (0.08 + 0.9 * t)
            rr = r * math.sin(math.pi * min(1.0, 0.15 + t * 0.95)) ** 0.8 * (0.5 + 0.5 * rng.random())
            a = rng.random() * 2 * math.pi
            pts.append((x + rr * math.cos(a), y + rr * math.sin(a), z))
        parts.append((f"cypress_{len(parts) + 1}/leaves", leaf_cards(pts, h * 0.14, rng)))

    for s in (-1.0, 1.0):
        for k in range(7):                                        # 广场外侧一行乔木
            broadleaf(-10000.0 + 800.0 * k + rng.random() * 200.0, s * (COURT_HALF_CM + 700.0 + rng.random() * 300.0),
                      1500.0 + rng.random() * 400.0)
        for k in range(5):                                        # 石梯外侧一行柏树
            spire(-5600.0 - 900.0 * k, s * (COURT_HALF_CM - 350.0), 900.0 + rng.random() * 200.0)
        for k in range(4):                                        # 楼两侧（翼外）乔木
            broadleaf(-4600.0 + 700.0 * k, s * (w.MAIN_LEN_CM / 2.0 + w.WING_LEN_CM + 900.0 + 500.0 * (k % 2)),
                      1700.0 + rng.random() * 300.0)
        for k in range(3):                                        # 广场前角乔木
            broadleaf(-10600.0 - 500.0 * k, s * (1200.0 + 900.0 * k), 1400.0 + rng.random() * 300.0)
    return parts + [("trees/bark", bark)]


def build_haiyantang_reference_scene() -> list[Part]:
    """参考图效果版海晏堂：史料版正楼 / 石梯 / 蓄水楼（改材质）+ 椭圆池群像 + 加饰 + 树木。"""
    court = [p for p in w.build_front_court()
             if p[0].startswith(("west_stairs/", "stone_leopard"))]  # 只留石跑梯、导水台、石豹
    return (_remap(w.build_main_hall()) + facade_ornament() + _remap(court) + stair_arcades() + build_reference_pool()
            + _remap(w.build_reservoir_hall()) + _remap(w.build_garden_fountains()) + build_trees()
            + [("viewpoint/viewpoint", w.beam(EYE, EYE_TARGET, 2.0))])
