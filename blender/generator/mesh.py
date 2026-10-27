"""mesh.py — 纯数据网格表示与基础形体工具。

几何模块的统一返回类型：参数 → ``Mesh(vertices, faces)``，不依赖 bpy，
可在无 Blender 的环境下运行与单测（项目编码规范「纯函数」）。

坐标：厘米、Z 向上（docs/decisions/ADR-0001）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

Vec3 = tuple[float, float, float]


@dataclass
class Mesh:
    """多边形网格（纯数据）。``faces`` 中的索引指向 ``vertices``。"""

    vertices: list[Vec3] = field(default_factory=list)
    faces: list[tuple[int, ...]] = field(default_factory=list)

    def merged(self, other: "Mesh") -> "Mesh":
        """返回与另一网格合并后的新网格（``other`` 的顶点索引整体后移）。"""
        off = len(self.vertices)
        return Mesh(
            vertices=self.vertices + [tuple(v) for v in other.vertices],
            faces=self.faces + [tuple(i + off for i in f) for f in other.faces],
        )

    def translated(self, dz: float = 0.0, dx: float = 0.0, dy: float = 0.0) -> "Mesh":
        """返回平移后的新网格。"""
        return Mesh(
            vertices=[(x + dx, y + dy, z + dz) for (x, y, z) in self.vertices],
            faces=list(self.faces),
        )

    def mirrored(self, axis: str) -> "Mesh":
        """返回关于 ``axis``（'x' 或 'y'）平面镜像后的新网格，并翻转面绕序。"""
        idx = {"x": 0, "y": 1}[axis]
        verts: list[Vec3] = []
        for v in self.vertices:
            vv = list(v)
            vv[idx] = -vv[idx]
            verts.append((vv[0], vv[1], vv[2]))
        return Mesh(vertices=verts, faces=[tuple(reversed(f)) for f in self.faces])

    def rotated_z(self, degrees: float) -> "Mesh":
        """返回绕 Z 轴旋转（度，逆时针）后的新网格。"""
        rad = math.radians(degrees)
        c, s = math.cos(rad), math.sin(rad)
        return Mesh(
            vertices=[(x * c - y * s, x * s + y * c, z) for (x, y, z) in self.vertices],
            faces=list(self.faces),
        )

    def validate(self) -> None:
        """基础合法性检查：坐标有限、面索引在范围内。组装前与单测中调用。"""
        n = len(self.vertices)
        for i, (x, y, z) in enumerate(self.vertices):
            if not all(map(math.isfinite, (x, y, z))):
                raise ValueError(f"顶点 {i} 含非有限坐标: {(x, y, z)}")
        for f in self.faces:
            if len(f) < 3:
                raise ValueError(f"面至少需要 3 个顶点: {f}")
            if len(set(f)) != len(f):
                raise ValueError(f"面含重复顶点索引（退化面）: {f}")
            for idx in f:
                if not 0 <= idx < n:
                    raise ValueError(f"面索引越界: {f}（顶点数 {n}）")

    def bounds(self) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        """返回轴对齐包围盒 ``((xmin, ymin, zmin), (xmax, ymax, zmax))``。"""
        if not self.vertices:
            raise ValueError("空网格没有包围盒")
        xs = [v[0] for v in self.vertices]
        ys = [v[1] for v in self.vertices]
        zs = [v[2] for v in self.vertices]
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def box(sx: float, sy: float, z0: float, z1: float, cx: float = 0.0, cy: float = 0.0) -> Mesh:
    """轴对齐长方体：平面尺寸 ``sx × sy``，中心 ``(cx, cy)``，z 从 ``z0`` 到 ``z1``。"""
    hx, hy = sx / 2.0, sy / 2.0
    v: list[Vec3] = [
        (cx - hx, cy - hy, z0), (cx + hx, cy - hy, z0),
        (cx + hx, cy + hy, z0), (cx - hx, cy + hy, z0),
        (cx - hx, cy - hy, z1), (cx + hx, cy - hy, z1),
        (cx + hx, cy + hy, z1), (cx - hx, cy + hy, z1),
    ]
    f: list[tuple[int, ...]] = [
        (0, 3, 2, 1),  # 底（外法向 −Z）
        (4, 5, 6, 7),  # 顶（+Z）
        (0, 1, 5, 4),  # −Y
        (1, 2, 6, 5),  # +X
        (2, 3, 7, 6),  # +Y
        (3, 0, 4, 7),  # −X
    ]
    return Mesh(vertices=v, faces=f)


def cylinder(
    z0: float, z1: float, radius: float, cx: float = 0.0, cy: float = 0.0, segments: int = 16
) -> Mesh:
    """竖直圆柱（柱身 / 柱础近似），轴线过 ``(cx, cy)``。"""
    if segments < 3:
        raise ValueError("segments 至少为 3")
    ring0: list[Vec3] = []
    ring1: list[Vec3] = []
    for k in range(segments):
        a = 2.0 * math.pi * k / segments
        ring0.append((cx + radius * math.cos(a), cy + radius * math.sin(a), z0))
        ring1.append((cx + radius * math.cos(a), cy + radius * math.sin(a), z1))
    verts = ring0 + ring1
    faces: list[tuple[int, ...]] = [tuple(range(segments - 1, -1, -1))]          # 底（−Z）
    faces.append(tuple(range(segments, 2 * segments)))                            # 顶（+Z）
    for k in range(segments):
        k2 = (k + 1) % segments
        faces.append((k, k2, segments + k2, segments + k))                        # 侧面
    return Mesh(vertices=verts, faces=faces)


def wedge(
    sx: float, sy: float, z0: float, z1_back: float, z1_front: float,
    cx: float = 0.0, cy: float = 0.0,
) -> Mesh:
    """顶面沿 Y 向倾斜的楔形体（垂带等）；front = −Y 侧，back = +Y 侧。

    底面 z = z0；顶面从后缘 z1_back 线性降到前缘 z1_front。
    """
    hx, hy = sx / 2.0, sy / 2.0
    v: list[Vec3] = [
        (cx - hx, cy - hy, z0), (cx + hx, cy - hy, z0),
        (cx + hx, cy + hy, z0), (cx - hx, cy + hy, z0),
        (cx - hx, cy - hy, z1_front), (cx + hx, cy - hy, z1_front),
        (cx + hx, cy + hy, z1_back), (cx - hx, cy + hy, z1_back),
    ]
    f: list[tuple[int, ...]] = [
        (0, 3, 2, 1),   # 底
        (4, 5, 6, 7),   # 顶（斜面）
        (0, 1, 5, 4),   # 前缘（−Y）
        (2, 3, 7, 6),   # 后缘（+Y）
        (1, 2, 6, 5),   # +X 侧（斜棱）
        (3, 0, 4, 7),   # −X 侧
    ]
    return Mesh(vertices=v, faces=f)


def prism(points: list[tuple[float, float]], z0: float, z1: float) -> Mesh:
    """多边形棱柱（湖面等）：points 为逆时针闭合多边形（不重复首点）。

    顶/底面为凹多边形时需先三角化；本项目的示意湖面均为凸多边形。
    """
    n = len(points)
    if n < 3:
        raise ValueError("多边形至少需要 3 个顶点")
    verts: list[Vec3] = [(x, y, z1) for (x, y) in points] + [(x, y, z0) for (x, y) in points]
    faces: list[tuple[int, ...]] = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
    for k in range(n):
        k2 = (k + 1) % n
        faces.append((k, k2, n + k2, n + k))
    return Mesh(vertices=verts, faces=faces)
