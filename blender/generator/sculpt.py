"""sculpt.py — 雕塑式形体：可「推拉」的椭球头部 + 渐细管（角、耳、喙、须、鬃），用于十二生肖兽首。

兽首造型依据现存 / 回归铜首的公开照片所见特征（牛首弯角宽吻、虎首短吻圆耳、猴首扁脸、猪首长吻鼻盘、
马首长脸竖耳带鬃、鼠首尖吻大圆耳、兔首长耳；龙蛇羊鸡狗五首下落不明，按清代同类铜饰通行造型推测），
为**简化雕塑**而非扫描，见 speculative S-023（史料版）与 ADR-0003（参考图效果版）。

局部坐标：+a 朝前（吻部方向）、+b 向左、+h 向上，原点在颈底中心；单位 cm（scale = 1 时）。
"""

from __future__ import annotations

import math
from pathlib import Path

from generator import mesh as mesh_mod

Vec = tuple[float, float, float]


def _norm(v: Vec) -> Vec:
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


def _cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


class Head:
    """可推拉的椭球（经纬网格）：brush 按方向或位置以高斯权重位移顶点。"""

    def __init__(self, centre: Vec, radii: Vec, seg: int = 24, rings: int = 16):
        cx, cy, cz = centre
        rx, ry, rz = radii
        self.centre = centre
        self.verts: list[list[float]] = [[cx, cy, cz - rz]]
        for i in range(1, rings):
            phi = math.pi * i / rings - math.pi / 2.0
            for k in range(seg):
                th = 2 * math.pi * k / seg
                self.verts.append([cx + rx * math.cos(phi) * math.cos(th), cy + ry * math.cos(phi) * math.sin(th),
                                   cz + rz * math.sin(phi)])
        self.verts.append([cx, cy, cz + rz])
        top = len(self.verts) - 1
        self.faces: list[tuple[int, ...]] = []
        for k in range(seg):
            k2 = (k + 1) % seg
            self.faces.append((0, 1 + k2, 1 + k))
            self.faces.append((top, 1 + (rings - 2) * seg + k, 1 + (rings - 2) * seg + k2))
        for i in range(rings - 2):
            a, b = 1 + i * seg, 1 + (i + 1) * seg
            for k in range(seg):
                k2 = (k + 1) % seg
                self.faces.append((a + k, a + k2, b + k2, b + k))

    def _dir(self, v: list[float]) -> Vec:
        return _norm((v[0] - self.centre[0], v[1] - self.centre[1], v[2] - self.centre[2]))

    def pull_dir(self, direction: Vec, amount: float, sigma: float, along: Vec | None = None) -> None:
        """方向笔刷：与 ``direction`` 夹角为 θ 的顶点位移 amount·exp(−(θ/σ)²)，沿 ``along``（缺省沿 direction）。"""
        d = _norm(direction)
        m = _norm(along) if along else d
        for v in self.verts:
            u = self._dir(v)
            ang = math.acos(max(-1.0, min(1.0, u[0] * d[0] + u[1] * d[1] + u[2] * d[2])))
            w = amount * math.exp(-(ang / sigma) ** 2)
            v[0] += m[0] * w
            v[1] += m[1] * w
            v[2] += m[2] * w

    def pull_pos(self, point: Vec, radius: float, move: Vec) -> None:
        """位置笔刷：距 ``point`` 为 r 的顶点位移 move·exp(−(r/radius)²)（眼窝、鼻孔、口缝）。"""
        for v in self.verts:
            r2 = (v[0] - point[0]) ** 2 + (v[1] - point[1]) ** 2 + (v[2] - point[2]) ** 2
            w = math.exp(-r2 / (radius * radius))
            v[0] += move[0] * w
            v[1] += move[1] * w
            v[2] += move[2] * w

    def taper_front(self, a0: float, side: float, height: float) -> None:
        """吻部收窄：a > a0 的顶点，侧向与竖向按距离线性缩放到 side / height 倍（吻端处）。"""
        amax = max(v[0] for v in self.verts)
        cy, cz = self.centre[1], self.centre[2]
        for v in self.verts:
            if v[0] > a0:
                t = (v[0] - a0) / max(1e-6, amax - a0)
                v[1] = cy + (v[1] - cy) * (1 + (side - 1) * t)
                v[2] = cz + (v[2] - cz) * (1 + (height - 1) * t)

    def flatten_front(self, a_max: float) -> None:
        """吻端截平（猪鼻盘）。"""
        for v in self.verts:
            v[0] = min(v[0], a_max)

    def tip(self) -> Vec:
        v = max(self.verts, key=lambda p: p[0])
        return (v[0], v[1], v[2])

    def mesh(self) -> mesh_mod.Mesh:
        return mesh_mod.Mesh(vertices=[tuple(v) for v in self.verts], faces=list(self.faces))


def tube(path: list[Vec], radii: list[float], flat: float = 1.0, up: Vec = (0.0, 0.0, 1.0),
         sides: int = 8) -> mesh_mod.Mesh:
    """沿折线的渐细管（角、喙、须、耳）：``flat`` < 1 时截面压扁（耳廓、鸡冠），压扁方向垂直于 ``up`` 与切向。"""
    verts: list[Vec] = []
    faces: list[tuple[int, ...]] = []
    n = len(path)
    for i, (p, r) in enumerate(zip(path, radii)):
        t = _norm(tuple(path[min(i + 1, n - 1)][k] - path[max(i - 1, 0)][k] for k in range(3)))
        side = _cross(t, up)
        if math.sqrt(sum(c * c for c in side)) < 1e-6:
            side = _cross(t, (1.0, 0.0, 0.0))
        side = _norm(side)
        nrm = _norm(_cross(side, t))
        for k in range(sides):
            th = 2 * math.pi * k / sides
            c, s = math.cos(th) * r * flat, math.sin(th) * r
            verts.append(tuple(p[j] + side[j] * c + nrm[j] * s for j in range(3)))
    for i in range(n - 1):
        for k in range(sides):
            k2 = (k + 1) % sides
            faces.append((i * sides + k, i * sides + k2, (i + 1) * sides + k2, (i + 1) * sides + k))
    faces.append(tuple(range(sides - 1, -1, -1)))
    faces.append(tuple(range((n - 1) * sides, n * sides)))
    return mesh_mod.Mesh(vertices=verts, faces=faces)


def _arc(p0: Vec, p1: Vec, bulge: Vec, n: int = 6) -> list[Vec]:
    """二次贝塞尔：p0 → p1，控制点 = 中点 + bulge（弯角、垂耳）。"""
    c = tuple((p0[k] + p1[k]) / 2 + bulge[k] for k in range(3))
    out = []
    for i in range(n + 1):
        t = i / n
        out.append(tuple((1 - t) ** 2 * p0[k] + 2 * (1 - t) * t * c[k] + t * t * p1[k] for k in range(3)))
    return out


def _pair(build) -> mesh_mod.Mesh:
    """左右对称件：build(side) 返回一侧（side = ±1）。"""
    return build(1.0).merged(build(-1.0))


def _ear(base: Vec, tip: Vec, width: float, bulge: Vec = (0.0, 0.0, 0.0), thick: float = 0.3) -> mesh_mod.Mesh:
    path = _arc(base, tip, bulge, 5)
    radii = [width * (0.55 + 0.45 * math.sin(math.pi * min(0.95, 0.2 + 0.8 * i / 5))) for i in range(6)]
    radii[-1] = width * 0.12
    return tube(path, radii, flat=thick, up=_norm((tip[0] - base[0], 0.0, 0.0)) if abs(tip[0] - base[0]) > 1 else (1.0, 0.0, 0.0))


def ellipsoid(centre: Vec, radii: Vec, tilt_deg: float = 0.0, seg: int = 18, rings: int = 12) -> Head:
    """以 centre 为心的椭球，绕侧向轴（b）前低后高倾斜 tilt_deg（吻部下垂）。"""
    e = Head((0.0, 0.0, 0.0), radii, seg, rings)
    t = math.radians(tilt_deg)
    c, s_ = math.cos(t), math.sin(t)
    for v in e.verts:
        a, h = v[0], v[2]
        v[0], v[2] = centre[0] + a * c - h * s_, centre[2] + a * s_ + h * c
        v[1] += centre[1]
    e.centre = centre
    return e


# 每首：颅骨半径；吻部 (中心 a, h)、半径 (前后, 侧, 高)、下倾角；是否加腮颊
_HEAD_SHAPES = {
    "rat": ((10.0, 9.0, 10.0), (10.0, -2.0), (10.0, 5.0, 5.0), -15.0, False),
    "ox": ((12.0, 11.5, 12.0), (11.0, -6.0), (9.5, 9.0, 8.0), -35.0, False),
    "tiger": ((12.5, 12.5, 12.0), (9.0, -3.0), (6.5, 9.0, 6.5), -10.0, True),
    "rabbit": ((10.0, 9.0, 10.5), (8.0, -3.0), (5.5, 6.5, 5.0), -15.0, True),
    "dragon": ((11.0, 10.0, 11.0), (14.0, -2.0), (12.0, 7.0, 6.0), -5.0, False),
    "snake": ((10.0, 9.0, 7.5), (9.0, -1.0), (9.0, 7.0, 5.0), 0.0, False),
    "horse": ((10.0, 9.0, 11.0), (13.0, -10.0), (15.0, 6.5, 7.0), -45.0, False),
    "goat": ((10.0, 8.5, 11.0), (11.0, -7.0), (11.0, 5.5, 6.0), -40.0, False),
    "monkey": ((11.5, 11.0, 12.5), (8.0, -5.0), (5.0, 7.0, 5.5), -10.0, False),
    "rooster": ((8.0, 7.5, 9.0), None, None, 0.0, False),
    "dog": ((10.5, 9.5, 11.0), (11.0, -4.0), (9.5, 5.5, 5.5), -15.0, False),
    "pig": ((12.0, 12.0, 11.5), (12.0, -3.0), (10.0, 7.0, 6.5), -5.0, False),
}


# 外部写实兽首（照片生成 3D / 扫描，经 tools/prepare_zodiac_heads.py 整理）：有则优先于雕塑兽首
HEAD_ASSET_DIR = Path(__file__).resolve().parents[2] / "assets" / "zodiac_heads"


def load_head_asset(kind: str, asset_dir: Path = HEAD_ASSET_DIR) -> tuple[mesh_mod.Mesh, Vec] | None:
    """读取 ``<asset_dir>/<kind>.obj``（局部 a 前 / b 左 / h 上），口部取中高度带内最靠前的顶点。"""
    path = asset_dir / f"{kind}.obj"
    if not path.exists():
        return None
    verts: list[Vec] = []
    faces: list[tuple[int, ...]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("v "):
            _, a, b, h = line.split()[:4]
            verts.append((float(a), float(b), float(h)))
        elif line.startswith("f "):
            idx = tuple(int(t.split("/")[0]) - 1 for t in line.split()[1:])
            if len(set(idx)) == len(idx) >= 3:
                faces.append(idx)
    if not verts or not faces:
        return None
    top = max(v[2] for v in verts)
    band = [v for v in verts if 0.25 * top <= v[2] <= 0.7 * top] or verts
    front = max(band, key=lambda v: v[0])
    return mesh_mod.Mesh(vertices=verts, faces=faces), (front[0], front[1], front[2])


FIGURE_ASSET_DIR = Path(__file__).resolve().parents[2] / "assets" / "zodiac_figures"


def load_figure_named(asset_dir: Path = FIGURE_ASSET_DIR) -> dict[str, tuple[mesh_mod.Mesh, Vec]]:
    """同 load_figure_assets，按文件名（生肖英文名）索引。"""
    paths = sorted(asset_dir.glob("*.obj")) if asset_dir.exists() else []
    return dict(zip((p.stem for p in paths), load_figure_assets(asset_dir)))


def load_figure_assets(asset_dir: Path = FIGURE_ASSET_DIR) -> list[tuple[mesh_mod.Mesh, Vec]]:
    """整尊铜像（单图生成 3D，经 tools/prepare_zodiac_figures.py 整理；局部 a 前 / b 左 / h 上，通高 1）。

    返回 [(网格, 吻端)]，按文件名排序；吻端取 72%–95% 高度带内最靠前的顶点（喷水口）。
    """
    out: list[tuple[mesh_mod.Mesh, Vec]] = []
    for path in sorted(asset_dir.glob("*.obj")) if asset_dir.exists() else []:
        verts: list[Vec] = []
        faces: list[tuple[int, ...]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("v "):
                _, a, b, h = line.split()[:4]
                verts.append((float(a), float(b), float(h)))
            elif line.startswith("f "):
                idx = tuple(int(t.split("/")[0]) - 1 for t in line.split()[1:])
                if len(set(idx)) == len(idx) >= 3:
                    faces.append(idx)
        band = [v for v in verts if 0.72 <= v[2] <= 0.95] or verts
        out.append((mesh_mod.Mesh(vertices=verts, faces=faces), max(band, key=lambda v: v[0])))
    return out


def headless(m: mesh_mod.Mesh, neck: float) -> mesh_mod.Mesh:
    """去掉整尊铜像原有的头（高于 ``neck`` 的顶点所在的面），留下身躯，以便换装生肖兽首。"""
    keep = [f for f in m.faces if all(m.vertices[i][2] <= neck for i in f)]
    used = sorted({i for f in keep for i in f})
    remap = {old: new for new, old in enumerate(used)}
    return mesh_mod.Mesh(vertices=[m.vertices[i] for i in used], faces=[tuple(remap[i] for i in f) for f in keep])


def _ring(verts: list[Vec], h0: float, h1: float) -> tuple[float, float, float]:
    """高度带 [h0, h1] 内顶点的水平中心与平均半径。"""
    band = [v for v in verts if h0 <= v[2] <= h1]
    ca = sum(v[0] for v in band) / len(band)
    cb = sum(v[1] for v in band) / len(band)
    r = sum(math.hypot(v[0] - ca, v[1] - cb) for v in band) / len(band)
    return ca, cb, r


def attach_head(body: mesh_mod.Mesh, neck: float, head: mesh_mod.Mesh, mouth: Vec,
                size: float = 1.25, sink: float = 0.06) -> tuple[mesh_mod.Mesh, mesh_mod.Mesh, Vec]:
    """把兽首装进整尊像去头后的颈口，返回 (身躯 + 脖颈, 兽首, 口部)，均在身躯局部单位（通高 1）中。

    兽首按被去掉的原头高度（1 − neck）× ``size`` 缩放、颈底中心对准颈口中心并插入颈口以下 ``sink``；
    脖颈自颈口内部向上直插兽首中部，底部与颈口同粗，填满断口。
    """
    torso = headless(body, neck)
    ca, cb, rb = _ring(torso.vertices, neck - 0.04, neck)
    hmin = min(v[2] for v in head.vertices)
    hmax = max(v[2] for v in head.vertices)
    ha, hb, _rh = _ring(head.vertices, hmin, hmin + 0.08 * (hmax - hmin))
    k = (1.0 - neck + sink) * size / max(hmax - hmin, 1e-9)
    z0 = neck - sink

    def tf(v: Vec) -> Vec:
        return (ca + (v[0] - ha) * k, cb + (v[1] - hb) * k, z0 + (v[2] - hmin) * k)

    placed = mesh_mod.Mesh(vertices=[tf(v) for v in head.vertices], faces=list(head.faces))
    # 铜质脖颈：自衣领内部向上直插兽首中部，不论兽首底部形状（下颌、颈管前沿）如何，颈部都连续不断
    hz = [v[2] for v in placed.vertices]
    head_h = max(hz) - min(hz)
    hc = (sum(v[0] for v in placed.vertices) / len(hz), sum(v[1] for v in placed.vertices) / len(hz))
    stem = tube([(ca, cb, neck - 0.05), ((ca + hc[0]) / 2, (cb + hc[1]) / 2, neck + 0.02),
                 (hc[0], hc[1], min(hz) + 0.45 * head_h)],
                [rb * 1.0, rb * 0.85, rb * 0.72], sides=20, up=(1.0, 0.0, 0.0))
    torso = torso.merged(stem)                                       # 脖颈属身躯（同材质），兽首自颈上起
    return torso, placed, tf(mouth)


def animal_head(kind: str) -> tuple[mesh_mod.Mesh, Vec]:
    """生肖兽首（含颈），返回 (网格, 口部位置)。

    有外部写实模型（``assets/zodiac_heads/<kind>.obj``）时用它；否则用雕塑兽首：
    颅骨 + 吻部 + 腮颊 + 眉弓 + 眼球 + 耳 / 角等附件。
    """
    asset = load_head_asset(kind)
    return asset if asset is not None else sculpted_head(kind)


def sculpted_head(kind: str) -> tuple[mesh_mod.Mesh, Vec]:
    """雕塑兽首（无写实模型时的后备）：颅骨 + 吻部 + 腮颊 + 眉弓 + 眼球 + 耳 / 角等附件。"""
    radii, mc, mr, tilt, cheeks = _HEAD_SHAPES[kind]
    rx, ry, rz = radii
    hc = (0.0, 0.0, 6.0 + rz)
    h = Head(hc, radii)
    for s in (-1.0, 1.0):                                         # 眼窝
        h.pull_pos((hc[0] + rx * 0.7, s * ry * 0.55, hc[2] + rz * 0.2), rx * 0.22, (-1.6, -s * 0.6, 0.0))
    h.pull_dir((-0.3, 0.0, -1.0), rz * 0.2, 0.7)                  # 颌下饱满
    out = h.mesh()
    for s in (-1.0, 1.0):                                         # 眼球与眉弓
        eye = (hc[0] + rx * 0.68, s * ry * 0.52, hc[2] + rz * 0.2)
        out = out.merged(ellipsoid(eye, (rx * 0.13, rx * 0.13, rx * 0.11), seg=10, rings=6).mesh())
        out = out.merged(ellipsoid((eye[0] - rx * 0.12, eye[1] * 0.95, eye[2] + rz * 0.17), (rx * 0.16, ry * 0.28, rz * 0.07),
                                   -10.0, seg=12, rings=6).mesh())
    tip: Vec
    if mc is not None:
        centre = (hc[0] + mc[0], 0.0, hc[2] + mc[1])
        m = ellipsoid(centre, mr, tilt)
        ta = math.radians(tilt)
        tip = (centre[0] + mr[0] * math.cos(ta), 0.0, centre[2] + mr[0] * math.sin(ta))
        for s in (-1.0, 1.0):                                     # 鼻孔
            m.pull_pos((tip[0], s * mr[1] * 0.35, tip[2] + mr[2] * 0.3), mr[2] * 0.25, (-1.5, 0.0, 0.0))
        m.pull_pos((tip[0], 0.0, tip[2] - mr[2] * 0.45), mr[1] * 0.5, (-1.2, 0.0, 0.0))   # 口缝
        if kind == "pig":
            m.flatten_front(tip[0] - 1.5)
            tip = (tip[0] - 1.5, 0.0, tip[2])
        out = out.merged(m.mesh())
        if kind in ("dragon", "tiger", "dog"):                    # 下颌（张口）
            jaw = (centre[0] - mr[0] * 0.1, 0.0, centre[2] - mr[2] * 0.85)
            out = out.merged(ellipsoid(jaw, (mr[0] * 0.8, mr[1] * 0.75, mr[2] * 0.4), tilt + 12.0).mesh())
        if kind in ("rat", "dog", "pig"):                         # 鼻头
            out = out.merged(ellipsoid((tip[0] - 0.5, 0.0, tip[2] + mr[2] * 0.2), (2.0, 2.4, 1.8), seg=10, rings=6).mesh())
    else:
        tip = (hc[0] + rx * 0.9, 0.0, hc[2] - 1.0)
    if cheeks:                                                    # 腮颊
        for s in (-1.0, 1.0):
            out = out.merged(ellipsoid((hc[0] + rx * 0.45, s * ry * 0.6, hc[2] - rz * 0.35),
                                       (rx * 0.45, ry * 0.42, rz * 0.38)).mesh())
    if kind == "monkey":                                          # 眉骨横脊
        out = out.merged(ellipsoid((hc[0] + rx * 0.72, 0.0, hc[2] + rz * 0.38), (rx * 0.25, ry * 0.85, rz * 0.12)).mesh())
    neck = tube([(0.0, 0.0, 0.0), (0.5, 0.0, 6.0), (1.0, 0.0, hc[2] - rz * 0.4)],
                [ry * 0.75, ry * 0.7, ry * 0.65], sides=12, up=(1.0, 0.0, 0.0))
    out = out.merged(neck)
    top = hc[2] + rz * 0.75

    if kind in ("rat", "monkey", "tiger"):                        # 圆耳（猴耳贴于两侧）
        big = {"rat": 7.5, "monkey": 4.5, "tiger": 4.5}[kind]
        lateral = kind == "monkey"
        out = out.merged(_pair(lambda s: _ear(
            (hc[0] - 1, s * ry * (0.9 if lateral else 0.55), hc[2] + (0 if lateral else rz * 0.65)),
            (hc[0] - 2, s * ry * (1.25 if lateral else 0.85), hc[2] + (2 if lateral else rz * 0.65 + big * 1.1)),
            big, thick=0.35)))
    if kind in ("ox", "goat", "dragon"):                          # 角
        if kind == "ox":
            horn = lambda s: tube(_arc((hc[0] - 2, s * ry * 0.6, top), (hc[0] + 3, s * (ry + 13), top + 9),
                                       (0.0, s * 3.0, -4.0)), [3.6, 3.2, 2.7, 2.1, 1.5, 0.9, 0.3])
        elif kind == "goat":
            horn = lambda s: tube(_arc((hc[0] + 1, s * ry * 0.4, top), (hc[0] - 8, s * (ry * 0.9), hc[2] - 4),
                                       (-8.0, s * 2.0, 10.0), 8), [3.0, 2.8, 2.5, 2.2, 1.8, 1.4, 1.0, 0.6, 0.2])
        else:
            horn = lambda s: tube(_arc((hc[0] - 2, s * ry * 0.4, top), (hc[0] - 16, s * ry * 0.8, top + 10),
                                       (0.0, 0.0, 4.0)), [2.4, 2.1, 1.8, 1.4, 1.0, 0.6, 0.2])
        out = out.merged(_pair(horn))
    if kind == "ox":                                              # 牛耳平伸
        out = out.merged(_pair(lambda s: _ear((hc[0] - 2, s * ry * 0.8, hc[2] + 2), (hc[0] - 3, s * (ry + 9), hc[2] + 1),
                                              4.0, thick=0.35)))
    if kind == "goat":                                            # 胡须
        chin = (tip[0] - 5.0, 0.0, tip[2] - 4.0)
        out = out.merged(tube([chin, (chin[0] - 1, 0.0, chin[2] - 5), (chin[0] - 0.5, 0.0, chin[2] - 9)],
                              [2.0, 1.4, 0.3], flat=0.5, up=(1.0, 0.0, 0.0)))
    if kind == "dragon":                                          # 龙须、鳍状耳、鬃
        out = out.merged(_pair(lambda s: tube(_arc((tip[0] - 2, s * 3.0, tip[2] + 1), (tip[0] - 4, s * 20.0, tip[2] - 6),
                                                   (4.0, s * 2.0, 6.0)), [1.2, 1.1, 0.9, 0.7, 0.5, 0.3, 0.1])))
        out = out.merged(_pair(lambda s: _ear((hc[0] - 4, s * ry * 0.85, hc[2] + 3), (hc[0] - 12, s * (ry + 6), hc[2] + 7),
                                              4.5, thick=0.3)))
        for k in range(4):
            out = out.merged(tube([(hc[0] - 6 - 3 * k, 0.0, top - 3 * k), (hc[0] - 11 - 3 * k, 0.0, top - 2 - 4 * k)],
                                  [2.5, 0.4], flat=0.35, up=(1.0, 0.0, 0.0)))
    if kind in ("rabbit", "horse", "dog", "pig", "goat"):         # 叶形耳：兔长竖、马尖竖、狗与猪下垂
        spec = {
            "rabbit": ((hc[0] - 3, 0.35, top - 1), (hc[0] - 8, 0.55, top + 24), (-2.0, 0.0, 2.0), 4.2),
            "horse": ((hc[0] - 3, 0.45, top - 1), (hc[0] - 2, 0.6, top + 10), (0.0, 0.0, 1.0), 3.2),
            "dog": ((hc[0] - 2, 0.6, top - 2), (hc[0] + 2, 1.15, hc[2] - 4), (0.0, 0.3, 4.0), 4.0),
            "pig": ((hc[0] - 1, 0.6, top - 1), (hc[0] + 7, 1.2, hc[2] + 1), (0.0, 0.3, 5.0), 6.0),
            "goat": ((hc[0] - 3, 0.8, hc[2] + 2), (hc[0] - 4, 1.4, hc[2] - 3), (0.0, 0.0, 1.0), 2.8),
        }[kind]
        (a0, b0, z0), (a1, b1, z1), bul, wid = spec
        out = out.merged(_pair(lambda s: _ear((a0, s * ry * b0, z0), (a1, s * ry * b1, z1),
                                              wid, (bul[0], s * bul[1] * ry, bul[2]))))
    if kind == "horse":                                           # 鬃：额前一绺 + 颈后一列
        out = out.merged(tube([(hc[0] + 2, 0.0, top + 1), (hc[0] + 7, 0.0, top - 3)], [2.5, 0.5], flat=0.4,
                              up=(0.0, 0.0, 1.0)))
        for k in range(6):
            z = top - 2 - 5 * k
            out = out.merged(tube([(hc[0] - rx * 0.8, 0.0, z), (hc[0] - rx * 0.8 - 6, 0.0, z - 6)], [3.0, 0.5],
                                  flat=0.35, up=(1.0, 0.0, 0.0)))
    if kind == "rooster":                                         # 喙、鸡冠、肉垂
        beak0 = (hc[0] + rx * 0.85, 0.0, hc[2] - 1)
        out = out.merged(tube([beak0, (beak0[0] + 5, 0.0, beak0[2] - 1), (beak0[0] + 9, 0.0, beak0[2] - 3)],
                              [3.0, 1.8, 0.2]))
        for k in range(5):
            a = hc[0] + 5 - 3.5 * k
            out = out.merged(tube([(a, 0.0, top - 1), (a + 0.5, 0.0, top + 5 + 2 * math.sin(k * 1.3))], [2.6, 1.0],
                                  flat=0.3, up=(1.0, 0.0, 0.0)))
        out = out.merged(_pair(lambda s: tube([(beak0[0] - 1, s * 2.0, beak0[2] - 3), (beak0[0] - 1, s * 2.5, beak0[2] - 10)],
                                              [2.4, 1.6], flat=0.4, up=(1.0, 0.0, 0.0))))
        tip = (beak0[0] + 9, 0.0, beak0[2] - 3)
    if kind == "snake":                                           # 信子分叉
        out = out.merged(_pair(lambda s: tube([(tip[0], 0.0, tip[2] - 2), (tip[0] + 5, s * 1.5, tip[2] - 3)],
                                              [0.6, 0.2])))
    mouth = (tip[0], tip[1], tip[2] - 2.0)
    return out, mouth


def lathe(profile: list[tuple[float, float]], cx: float, cy: float, z0: float, seg: int = 12) -> mesh_mod.Mesh:
    """旋转体：``profile`` 为自下而上的 (半径, 高)。"""
    rings = [[(cx + r * math.cos(2 * math.pi * k / seg), cy + r * math.sin(2 * math.pi * k / seg), z0 + h)
              for k in range(seg)] for r, h in profile]
    verts = [v for ring in rings for v in ring]
    faces: list[tuple[int, ...]] = []
    for i in range(len(rings) - 1):
        for k in range(seg):
            k2 = (k + 1) % seg
            faces.append((i * seg + k, i * seg + k2, (i + 1) * seg + k2, (i + 1) * seg + k))
    faces.append(tuple(range(seg - 1, -1, -1)))
    faces.append(tuple(range((len(rings) - 1) * seg, len(rings) * seg)))
    return mesh_mod.Mesh(vertices=verts, faces=faces)


def folded_lathe(profile: list[tuple[float, float]], cx: float, cy: float, z0: float, seg: int,
                 folds: int, depth: float, fold_top: float) -> mesh_mod.Mesh:
    """带衣褶的旋转体：高度 ``fold_top`` 以下的截面半径按 cos(folds·θ) 起伏（袍裾垂褶）。"""
    m = lathe(profile, cx, cy, z0, seg=seg)
    verts = []
    for vx, vy, vz in m.vertices:
        dx, dy = vx - cx, vy - cy
        k = depth * max(0.0, 1.0 - (vz - z0) / fold_top) if fold_top > 0 else 0.0
        f = 1.0 + k * math.cos(folds * math.atan2(dy, dx))
        verts.append((cx + dx * f, cy + dy * f, vz))
    return mesh_mod.Mesh(vertices=verts, faces=m.faces)


ROBE_PROFILE = [(40, 0), (42, 8), (40, 25), (34, 45), (28, 62), (25, 75), (23, 85), (20, 92), (14, 98), (9, 102)]
ROBE_HEIGHT = 102.0              # 坐像袍身至领口高（scale = 1，cm）


def robed_body(x: float, y: float, z: float, face: tuple[float, float], s: float) -> mesh_mod.Mesh:
    """石雕袍服坐像身躯（生肖像「人身」）：垂褶袍身、前伸的膝、垂于膝前的袍裾、肩、广袖、拱手、交领。"""
    out = folded_lathe([(r * s, h * s) for r, h in ROBE_PROFILE], x, y, z, seg=16, folds=9, depth=0.07, fold_top=70 * s)
    local = ellipsoid((16.0, 0.0, 40.0), (22.0, 25.0, 10.0), -6.0).mesh()                # 膝
    local = local.merged(tube([(26.0, 0.0, 42.0), (33.0, 0.0, 22.0), (35.0, 0.0, 3.0)],
                              [20.0, 23.0, 26.0], flat=0.45, up=(0.0, 0.0, 1.0), sides=12))  # 袍裾
    local = local.merged(ellipsoid((0.0, 0.0, 88.0), (13.0, 29.0, 10.0)).mesh())             # 肩
    for side in (-1.0, 1.0):                                      # 广袖：肩 → 肘 → 双手拱于膝上，袖口渐宽
        local = local.merged(tube([(0.0, side * 24.0, 88.0), (8.0, side * 28.0, 70.0), (14.0, side * 27.0, 60.0),
                                   (28.0, side * 13.0, 55.0)], [9.0, 10.5, 12.5, 14.0], sides=12, up=(0.0, 0.0, 1.0)))
    local = local.merged(ellipsoid((33.0, 0.0, 55.0), (6.0, 8.0, 6.0)).mesh())               # 拱手
    out = out.merged(place(local, x, y, z, face, s))
    return out.merged(lathe([(12 * s, 0), (17 * s, 3 * s), (13 * s, 7 * s)], x, y, z + 96 * s, seg=12))  # 交领


STANDING_PROFILE = [(24, 0), (26, 5), (25, 18), (22, 45), (20, 75), (19, 98), (19.5, 112), (21, 122),
                    (17, 130), (10, 135)]
STANDING_HEIGHT = 135.0          # 立像袍身至领口高（scale = 1，cm）


def standing_robe(x: float, y: float, z: float, face: tuple[float, float], s: float) -> mesh_mod.Mesh:
    """立姿长袍像身躯（参考图效果版的全铜生肖像）：深竖褶垂地长袍、溜肩、垂袖、拱手、交领。"""
    out = folded_lathe([(r * s, h * s) for r, h in STANDING_PROFILE], x, y, z, seg=32, folds=13, depth=0.16,
                       fold_top=118 * s)
    local = ellipsoid((0.0, 0.0, 122.0), (11.0, 22.0, 7.0)).mesh()                         # 溜肩
    for side in (-1.0, 1.0):
        local = local.merged(tube([(0.0, side * 19.0, 122.0), (5.0, side * 22.0, 104.0), (12.0, side * 14.0, 99.0),
                                   (17.0, side * 5.0, 101.0)], [7.0, 8.5, 10.0, 10.5], sides=12, up=(0.0, 0.0, 1.0)))  # 袖
        local = local.merged(tube([(5.0, side * 22.0, 104.0), (6.0, side * 23.0, 82.0), (5.0, side * 21.0, 62.0)],
                                  [9.0, 11.0, 12.0], flat=0.45, sides=12, up=(1.0, 0.0, 0.0)))   # 垂袖
    local = local.merged(ellipsoid((19.0, 0.0, 101.0), (5.0, 8.0, 5.5)).mesh())              # 拱手
    out = out.merged(place(local, x, y, z, face, s))
    return out.merged(lathe([(10 * s, 0), (14 * s, 2 * s), (10 * s, 5 * s)], x, y, z + 132 * s, seg=12))  # 交领


def place(m: mesh_mod.Mesh, x: float, y: float, z: float, face: tuple[float, float], scale: float) -> mesh_mod.Mesh:
    """局部 (a 前, b 左, h 上) → 平面坐标：朝向 ``face``（单位向量），缩放 ``scale``，原点放到 (x, y, z)。"""
    fx, fy = face
    px, py = -fy, fx
    return mesh_mod.Mesh(vertices=[(x + (fx * a + px * b) * scale, y + (fy * a + py * b) * scale, z + h * scale)
                                   for a, b, h in m.vertices], faces=list(m.faces))


def place_point(p: Vec, x: float, y: float, z: float, face: tuple[float, float], scale: float) -> Vec:
    fx, fy = face
    px, py = -fy, fx
    a, b, h = p
    return (x + (fx * a + px * b) * scale, y + (fy * a + py * b) * scale, z + h * scale)
