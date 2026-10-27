"""gltf.py — 极简 glTF 2.0 (.glb) 写出器（纯 Python，无第三方依赖）。

用途：把纯数据网格（generator.mesh.Mesh）导出为浏览器可加载的 glb，
不依赖 Blender——与 assemble.py 的 bpy 导出路径共用同一几何层。

坐标换算只在导出层做一次（docs/decisions/ADR-0001）：
- 单位：场景 1 单位 = 1 cm → glTF 以米计 → 数值 ÷ 100；
- 轴向：项目 Z-up、建筑正面朝 −Y → glTF Y-up：(x, y, z) → (x, z, −y)。

多边形：扇形三角化 (v0, vi, vi+1)。本项目构件面均为凸平面多边形，适用。
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from typing import Iterator

from generator.mesh import Mesh

MAGIC_GLB = 0x46546C67       # 'glTF'
CHUNK_JSON = 0x4E4F534A      # 'JSON'
CHUNK_BIN = 0x004E4942       # 'BIN\0'
COMPONENT_FLOAT = 5126
COMPONENT_UINT16 = 5123
COMPONENT_UINT32 = 5125
MODE_TRIANGLES = 4
TARGET_ARRAY_BUFFER = 34962
TARGET_ELEMENT_ARRAY_BUFFER = 34963

CM_TO_M = 0.01


@dataclass(frozen=True)
class Primitive:
    """一个 glTF primitive：命名的纯数据网格 + 占位颜色（线性 RGB 0–1）。"""

    name: str
    mesh: Mesh
    color: tuple[float, float, float]


def _transform(v: tuple[float, float, float]) -> tuple[float, float, float]:
    """cm / Z-up → m / Y-up（唯一一次单位与轴向换算）。"""
    x, y, z = v
    return (x * CM_TO_M, z * CM_TO_M, -y * CM_TO_M)


def _triangulate(faces) -> Iterator[tuple[int, int, int]]:
    """扇形三角化：n 边形 → n−2 个三角形，保持绕序。"""
    for f in faces:
        for k in range(1, len(f) - 1):
            yield f[0], f[k], f[k + 1]


def _node_extras(prim: Primitive) -> dict:
    extras: dict = {"label": prim.name}
    key = {"jet": "jet", "viewpoint": "viewpoint"}.get(prim.name.rsplit("/", 1)[-1])
    if key and len(prim.mesh.vertices) >= 8:                     # 两端点标记：喷水（喷口→落点）、人视（眼→注视点）
        vs = [_transform(v) for v in prim.mesh.vertices[:8]]
        p0 = [sum(v[k] for v in vs[:4]) / 4.0 for k in range(3)]
        p1 = [sum(v[k] for v in vs[4:8]) / 4.0 for k in range(3)]
        extras[key] = [round(c, 4) for c in p0 + p1]
    return extras


def build_glb(primitives: list[Primitive]) -> bytes:
    """把若干 primitive 打包为单个 .glb 字节流（JSON + BIN 双 chunk）。"""
    bin_parts: list[bytes] = []
    offset = 0
    buffer_views: list[dict] = []
    accessors: list[dict] = []
    meshes: list[dict] = []
    materials: list[dict] = []

    def add_view(blob: bytes, target: int) -> int:
        nonlocal offset
        pad = (-offset) % 4
        if pad:
            bin_parts.append(b"\x00" * pad)
            offset += pad
        view: dict = {"buffer": 0, "byteOffset": offset, "byteLength": len(blob)}
        if target:
            view["target"] = target
        buffer_views.append(view)
        bin_parts.append(blob)
        offset += len(blob)
        return len(buffer_views) - 1

    for i, prim in enumerate(primitives):
        prim.mesh.validate()

        verts_g = [_transform(v) for v in prim.mesh.vertices]
        positions = b"".join(struct.pack("<3f", *v) for v in verts_g)
        pos_view = add_view(positions, TARGET_ARRAY_BUFFER)
        accessors.append(
            {
                "bufferView": pos_view,
                "componentType": COMPONENT_FLOAT,
                "count": len(verts_g),
                "type": "VEC3",
                # POSITION accessor 必须给出 min/max（glTF 2.0 规范要求）
                "min": [min(v[0] for v in verts_g), min(v[1] for v in verts_g), min(v[2] for v in verts_g)],
                "max": [max(v[0] for v in verts_g), max(v[1] for v in verts_g), max(v[2] for v in verts_g)],
            }
        )
        pos_acc = len(accessors) - 1

        tris = list(_triangulate(prim.mesh.faces))
        if len(verts_g) <= 65535:
            pack = struct.Struct("<H")
            comp = COMPONENT_UINT16
        else:
            pack = struct.Struct("<I")
            comp = COMPONENT_UINT32
        indices_blob = b"".join(pack.pack(t) for tri in tris for t in tri)
        idx_view = add_view(indices_blob, TARGET_ELEMENT_ARRAY_BUFFER)
        accessors.append(
            {
                "bufferView": idx_view,
                "componentType": comp,
                "count": len(tris) * 3,
                "type": "SCALAR",
            }
        )
        idx_acc = len(accessors) - 1

        materials.append(
            {
                "name": prim.name,
                "pbrMetallicRoughness": {
                    "baseColorFactor": [prim.color[0], prim.color[1], prim.color[2], 1.0],
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.9,
                },
                "doubleSided": True,
            }
        )
        meshes.append(
            {
                "name": prim.name,
                "primitives": [
                    {"attributes": {"POSITION": pos_acc}, "indices": idx_acc, "material": i, "mode": MODE_TRIANGLES}
                ],
            }
        )

    # 网格名可能被查看器净化（three.js 会去掉 '/' 等字符），完整标签另存 extras.label；
    # 喷水标记另存两端点 extras.jet（米，glTF 坐标），不依赖顶点顺序（经 Blender 往返后顺序会变）
    nodes = [{"mesh": i, "name": p.name, "extras": _node_extras(p)} for i, p in enumerate(primitives)]
    gltf_doc = {
        "asset": {"version": "2.0", "generator": "yuanmingyuan-3d / generator.gltf"},
        "scene": 0,
        "scenes": [{"name": "scene", "nodes": list(range(len(nodes)))}],
        "nodes": nodes,
        "meshes": meshes,
        "materials": materials,
        "accessors": accessors,
        "bufferViews": buffer_views,
        "buffers": [{"byteLength": offset}],
    }

    json_blob = json.dumps(gltf_doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    json_blob += b" " * ((-len(json_blob)) % 4)  # JSON chunk 以空格补齐到 4 字节
    bin_blob = b"".join(bin_parts)
    bin_blob += b"\x00" * ((-len(bin_blob)) % 4)  # BIN chunk 以 0 补齐

    total = 12 + 8 + len(json_blob) + 8 + len(bin_blob)
    return (
        struct.pack("<III", MAGIC_GLB, 2, total)
        + struct.pack("<II", len(json_blob), CHUNK_JSON)
        + json_blob
        + struct.pack("<II", len(bin_blob), CHUNK_BIN)
        + bin_blob
    )


def parse_glb(blob: bytes) -> tuple[int, dict, bytes]:
    """读取 glb：返回 (version, JSON 文档, BIN 数据)。供测试与自查使用。"""
    if len(blob) < 20:
        raise ValueError("glb 过短")
    magic, version, total = struct.unpack_from("<III", blob, 0)
    if magic != MAGIC_GLB:
        raise ValueError(f"magic 不符: {magic:#x}")
    if total != len(blob):
        raise ValueError(f"总长不符: 头 {total} vs 实际 {len(blob)}")
    json_len, json_type = struct.unpack_from("<II", blob, 12)
    if json_type != CHUNK_JSON:
        raise ValueError("首 chunk 不是 JSON")
    doc = json.loads(blob[20:20 + json_len].decode("utf-8"))
    bin_off = 20 + json_len
    bin_len, bin_type = struct.unpack_from("<II", blob, bin_off)
    if bin_type != CHUNK_BIN:
        raise ValueError("第二 chunk 不是 BIN")
    return version, doc, blob[bin_off + 8:bin_off + 8 + bin_len]
