"""terrain.py — 水系地形：三角剖分、水面板、OSM 实测水域装载。

两套来源并存：
- 内置示意多边形（POLYGONS，如 fuhai 八边形）——用于 data/gardens/yuanmingyuan_preview.yaml
  的 lakes.polygon（示意版，S-028）；
- OpenStreetMap 实测水域（tools/osm_to_terrain.py 生成 data/terrain/water_polygons.json，
  © OSM 贡献者 ODbL；load_polygons 装载）——用于 data/gardens/sanyuan_osm.yaml 的
  garden.terrain（实测版，S-028）。

真实岸线比例可信；多边形形状经 OSM 简化（间距 ≥ 12 m），殿址精度仍为工作假设。
"""

from __future__ import annotations

import json
from pathlib import Path

from generator import mesh as mesh_mod

WATER_DEPTH_CM = 30.0  # 水面板厚度（cm，示意）

# ---------------------------------------------------------------------------
# 内置示意多边形（示意版预览用）
# ---------------------------------------------------------------------------

# 福海示意多边形（局部坐标，中心 0，逆时针；八边形近似圆角方形）
# 尺寸：11000 × 9000 cm（工作假设，与后湖 2200 宽约成 5:1）
FUHAI_POLYGON: tuple[tuple[float, float], ...] = (
    (-5500.0, -2300.0),
    (-3300.0, -4500.0),
    (3300.0, -4500.0),
    (5500.0, -2300.0),
    (5500.0, 2300.0),
    (3300.0, 4500.0),
    (-3300.0, 4500.0),
    (-5500.0, 2300.0),
)

POLYGONS: dict[str, tuple[tuple[float, float], ...]] = {
    "fuhai": FUHAI_POLYGON,
}

# ---------------------------------------------------------------------------
# 三角剖分（耳切法，支持凹多边形，自动统一绕序为逆时针）
# ---------------------------------------------------------------------------


def _signed_area(pts: list[tuple[float, float]]) -> float:
    s = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        s += x0 * y1 - x1 * y0
    return s / 2.0


def triangulate(points) -> list[tuple[int, int, int]]:
    """简单多边形耳切三角剖分：返回顶点索引三角形列表（绕序 CCW）。

    支持凹多边形；不支持带洞多边形（湖中岛后续以独立地块表达）。
    """
    pts = [(float(x), float(y)) for x, y in points]
    n = len(pts)
    if n < 3:
        raise ValueError(f"多边形至少需要 3 个顶点，收到 {n}")
    if _signed_area(pts) < 0:
        pts = pts[::-1]  # 统一为逆时针

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    idx = list(range(n))
    tris: list[tuple[int, int, int]] = []
    guard = 0
    while len(idx) > 3 and guard < 20 * n:
        guard += 1
        clipped = False
        for i in range(len(idx)):
            i0, i1, i2 = idx[i - 1], idx[i], idx[(i + 1) % len(idx)]
            p0, p1, p2 = pts[i0], pts[i1], pts[i2]
            if cross(p0, p1, p2) <= 1e-12:
                continue  # 反射顶点或共线，不能剪
            # 其余顶点不得落入该三角形内
            contains_other = False
            for j in idx:
                if j in (i0, i1, i2):
                    continue
                pj = pts[j]
                d1 = cross(p0, p1, pj)
                d2 = cross(p1, p2, pj)
                d3 = cross(p2, p0, pj)
                if d1 >= -1e-9 and d2 >= -1e-9 and d3 >= -1e-9:
                    contains_other = True
                    break
            if contains_other:
                continue
            tris.append((i0, i1, i2))
            idx.remove(i1)
            clipped = True
            break
        if not clipped:
            break  # 剩余部分退化（自交等），停止以免死循环
    if len(idx) == 3:
        tris.append((idx[0], idx[1], idx[2]))
    return tris


def polygon_slab(coords, z_top: float = 0.0, depth: float = WATER_DEPTH_CM) -> mesh_mod.Mesh:
    """水面板：多边形棱柱（顶面 z_top，底面 z_top − depth；支持凹多边形）。"""
    pts = [(float(x), float(y)) for x, y in coords]
    if len(pts) < 3:
        raise ValueError(f"多边形至少需要 3 个顶点，收到 {len(pts)}")
    tris = triangulate(pts)
    n = len(pts)
    verts = [(x, y, z_top) for (x, y) in pts] + [(x, y, z_top - depth) for (x, y) in pts]
    faces: list[tuple[int, ...]] = []
    for (i0, i1, i2) in tris:
        faces.append((i0, i1, i2))            # 顶面（CCW → +Z）
        faces.append((i0, i2, i1))            # 底面（−Z）
    for k in range(n):
        k2 = (k + 1) % n
        faces.append((k, k2, n + k2, n + k))  # 侧壁
    return mesh_mod.Mesh(vertices=verts, faces=faces)


# ---------------------------------------------------------------------------
# OSM 实测水域装载（data/terrain/water_polygons.json）
# ---------------------------------------------------------------------------


def load_polygons(path, names=()) -> list[dict]:
    """装载 OSM 水域 JSON；``names`` 为 name 或 id 过滤器（空 = 全部）。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    wanted = {str(x) for x in (names or ())}
    out: list[dict] = []
    for p in data.get("polygons", []):
        if wanted and p.get("name") not in wanted and p.get("id") not in wanted:
            continue
        out.append(p)
    return out
