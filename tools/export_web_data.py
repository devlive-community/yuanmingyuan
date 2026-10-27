#!/usr/bin/env python3
"""export_web_data.py — 为网页端（web/app，React）导出模型与元数据。

输出到 web/app/src/generated/：
- ``models/{id}.glb``：三园总图、各景、生成器样例，每个模型一个 glb；
- ``manifest.json``：模型列表、各景建筑元数据（参数、evidence 置信度、YAML 头注释）、
  总图水域名称。键一律为英文 id（景 id / 建筑 key / OSM 水域 id），与网格标签一致；
  中文名称只作为数据值，由页面渲染。

用法：python3 tools/export_web_data.py   （或在 web/app 下 npm run data）
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT / "blender"))
sys.path.insert(0, str(_ROOT / "blender" / "export"))  # 复用 export_glb 的组装与占位色

from export_glb import garden_to_primitives, scene_to_primitives  # noqa: E402
from generator import config as config_mod  # noqa: E402
from generator import gltf as gltf_mod  # noqa: E402
from generator import plan as plan_mod  # noqa: E402
from generator import scene as scene_mod  # noqa: E402
from generator import terrain as terrain_mod  # noqa: E402

GARDEN_PATH = _ROOT / "data" / "gardens" / "sanyuan_osm.yaml"
SAMPLE_PATHS = (
    _ROOT / "data" / "samples" / "roof_types.yaml",
    _ROOT / "data" / "samples" / "xiaoshi.yaml",
)
# 同一景的另一版本（页面在该景信息卡上切换，不单列于景区目录、不进总图）：路径 → 所属景 id
VARIANT_PATHS = {
    _ROOT / "data" / "scenes" / "haiyantang_reference.yaml": "haiyantang",   # 参考图效果版（非史料，ADR-0003）
}
OUT_DIR = _ROOT / "web" / "app" / "src" / "generated"
TEXTURE_SRC = _ROOT / "assets" / "polyhaven"          # Poly Haven CC0 实拍材质（2k JPG + HDR）
TEXTURE_SIZE = 1024                                    # 打包进网页时缩到 1k WebP

# 烘焙光照的景（Blender 倒角 + 天光光照贴图 + meshopt 压缩）；缺 Blender 时退回未烘焙模型
BAKED_SCENES = {"haiyantang", "haiyantang_reference"}
MESHOPT_DIR = _ROOT / "build" / "meshopt"   # 未烘焙模型的压缩缓存
BAKE_SAMPLES = 128
BLENDER = Path(os.environ.get("BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender"))
BAKE_DIR = _ROOT / "build" / "baked"
BAKE_SCRIPTS = (_ROOT / "blender" / "render" / "bake_scene.py", _ROOT / "blender" / "render" / "cycles_render.py")


def header_comment(path: Path) -> str:
    """YAML 文件开头的连续注释块（去掉 '# '），作为景/建筑说明。"""
    out: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("#"):
            break
        out.append(line[1:].removeprefix(" "))
    return "\n".join(out).strip()


def building_meta(path: Path, role: str) -> dict:
    """单栋建筑元数据：参数摘要、平面尺寸、evidence。``role`` 为景内角色名（显示用）。"""
    p = config_mod.load_building(path)
    pl = plan_mod.build_plan(p)
    if p.grade == "大式":
        module = f"斗口 {pl.doukou_cm / 3.2:.1f} 寸（{pl.doukou_cm:.1f} cm）"
    else:
        module = f"明间 {p.ming_bay_chi:g} 尺（小式）"
    return {
        "id": p.id,
        "role": role,
        "name": p.name,
        "grade": p.grade,
        "module": module,
        "bays": p.bays,
        "depth_bays": p.depth_bays,
        "roof": p.roof + ("（重檐）" if p.double_eave else ""),
        "brackets": p.bracket_set,
        "enclosure": p.enclosure,
        "corridor": p.corridor,
        "stories": p.stories,
        "platform_chi": p.platform_height_chi,
        "length_m": round(pl.length / 100.0, 2),
        "width_m": round(pl.width / 100.0, 2),
        "column_m": round(pl.column_height_cm / 100.0, 2),
        "evidence": [dict(e) for e in p.evidence],
        "notes": header_comment(path),
        "file": str(path.resolve().relative_to(_ROOT)),
    }


def scene_meta(path: Path) -> tuple[config_mod.Scene, dict]:
    sc = config_mod.load_scene(path)
    # 键与网格标签一致：建筑 key（英文 id，重复引用加 _2…）
    buildings = {
        key: building_meta(bpath, sb.role) for key, sb, bpath in scene_mod.building_keys(sc, path)
    }
    return sc, {
        "id": sc.id,
        "name": sc.name,
        "special": sc.special,
        "notes": header_comment(path),
        "file": str(path.resolve().relative_to(_ROOT)),
        "buildings": buildings,
    }


def export_textures() -> int:
    """实拍材质：2k JPG → 1k WebP；HDR 天空原样复制。返回写出字节数。"""
    from PIL import Image

    out = OUT_DIR / "textures"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    total = 0
    for src in sorted(TEXTURE_SRC.glob("*.jpg")):
        dst = out / (src.stem + ".webp")
        Image.open(src).convert("RGB").resize((TEXTURE_SIZE, TEXTURE_SIZE), Image.LANCZOS).save(
            dst, "WEBP", quality=82)
        total += dst.stat().st_size
    for src in TEXTURE_SRC.glob("*.hdr"):
        shutil.copyfile(src, out / "sky.hdr")
        total += src.stat().st_size
    return total


def baked_glb(model_id: str, raw: bytes) -> bytes | None:
    """Blender 烘焙 + meshopt 压缩，按内容哈希缓存；失败或缺 Blender 时返回 None。"""
    if not BLENDER.exists():
        print(f"[web-data] 未找到 Blender，{model_id} 用未烘焙模型")
        return None
    key = hashlib.sha256(raw + b"".join(p.read_bytes() for p in BAKE_SCRIPTS) +
                         str(BAKE_SAMPLES).encode()).hexdigest()
    BAKE_DIR.mkdir(parents=True, exist_ok=True)
    out = BAKE_DIR / f"{model_id}.opt.glb"
    key_file = BAKE_DIR / f"{model_id}.key"
    if out.exists() and key_file.exists() and key_file.read_text() == key:
        return out.read_bytes()
    raw_path, baked = BAKE_DIR / f"{model_id}.raw.glb", BAKE_DIR / f"{model_id}.glb"
    raw_path.write_bytes(raw)
    print(f"[web-data] 烘焙 {model_id}（Blender Cycles，约数分钟）…")
    r = subprocess.run([str(BLENDER), "-b", "--factory-startup", "-P", str(BAKE_SCRIPTS[0]), "--",
                        "--glb", str(raw_path), "--out-glb", str(baked), "--samples", str(BAKE_SAMPLES)],
                       capture_output=True, text=True)
    if r.returncode != 0 or not baked.exists():
        print(f"[web-data] 烘焙失败，{model_id} 用未烘焙模型：\n{r.stdout[-2000:]}{r.stderr[-2000:]}")
        return None
    r = subprocess.run(["npx", "gltf-transform", "meshopt", str(baked), str(out)],
                       cwd=_ROOT / "web" / "app", capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        print(f"[web-data] meshopt 压缩失败，{model_id} 用未压缩烘焙模型：\n{r.stderr[-2000:]}")
        return baked.read_bytes()
    key_file.write_text(key)
    return out.read_bytes()


def meshopt_glb(model_id: str, raw: bytes) -> bytes:
    """未烘焙模型的 meshopt 压缩（顶点量化 + 熵编码，浏览器端解码），按内容哈希缓存；失败时返回原件。"""
    key = hashlib.sha256(raw).hexdigest()
    MESHOPT_DIR.mkdir(parents=True, exist_ok=True)
    out, key_file = MESHOPT_DIR / f"{model_id}.glb", MESHOPT_DIR / f"{model_id}.key"
    if out.exists() and key_file.exists() and key_file.read_text() == key:
        return out.read_bytes()
    raw_path = MESHOPT_DIR / f"{model_id}.raw.glb"
    raw_path.write_bytes(raw)
    r = subprocess.run(["npx", "gltf-transform", "meshopt", str(raw_path), str(out)],
                       cwd=_ROOT / "web" / "app", capture_output=True, text=True)
    raw_path.unlink()
    if r.returncode != 0 or not out.exists():
        print(f"[web-data] meshopt 压缩失败，{model_id} 用未压缩模型：\n{r.stderr[-2000:]}")
        return raw
    key_file.write_text(key)
    return out.read_bytes()


def write_glb(prims: list[gltf_mod.Primitive], model_id: str) -> int:
    blob = gltf_mod.build_glb(prims)
    baked = baked_glb(model_id, blob) if model_id in BAKED_SCENES else None
    blob = baked or meshopt_glb(model_id, blob)
    (OUT_DIR / "models" / f"{model_id}.glb").write_bytes(blob)
    return len(blob)


def main() -> int:
    if (OUT_DIR / "models").exists():
        shutil.rmtree(OUT_DIR / "models")
    (OUT_DIR / "models").mkdir(parents=True)

    garden = config_mod.load_garden(GARDEN_PATH)
    total = write_glb(garden_to_primitives(garden, str(GARDEN_PATH)), garden.id)
    waters: dict[str, str] = {}
    if garden.terrain is not None:
        tg = garden.terrain
        for wp in terrain_mod.load_polygons(scene_mod.resolve_ref(GARDEN_PATH, tg.file), tg.names):
            waters[wp["id"]] = wp["name"] or wp["id"]
    models: list[dict] = [{
        "id": garden.id, "title": garden.name, "group": "overview", "scene": None,
        "notes": header_comment(GARDEN_PATH), "sceneCount": len(garden.scenes),
    }]
    scenes: dict[str, dict] = {}

    scene_paths = [scene_mod.resolve_ref(GARDEN_PATH, gs.ref) for gs in garden.scenes]
    for group, paths in (("scenes", scene_paths), ("scenes", list(VARIANT_PATHS)), ("samples", SAMPLE_PATHS)):
        for sp in paths:
            sc, m = scene_meta(sp)
            scenes[sc.id] = m
            total += write_glb(scene_to_primitives(sc, str(sp)), sc.id)
            models.append({"id": sc.id, "title": sc.name, "group": group, "scene": sc.id,
                           "notes": m["notes"], "sceneCount": 0, "variantOf": VARIANT_PATHS.get(sp)})

    tex_bytes = export_textures() if TEXTURE_SRC.exists() else 0
    print(f"[web-data] 材质纹理 {tex_bytes:,} 字节")
    manifest = {"models": models, "scenes": scenes, "waters": waters}
    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"[web-data] {OUT_DIR}：{len(models)} 个模型，glb 合计 {total:,} 字节")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
