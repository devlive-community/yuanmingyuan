"""tsr_generate.py — 用 TripoSR（本机）从单张图生成网格：去背景 → 前景居中 → 推理 → marching cubes → OBJ。

用法（项目根目录）：

    .venv/bin/python -I tools/tsr_generate.py assets/zodiac_figures/raw assets/zodiac_figures/raw/ref_L1.png …

输出 <输出目录>/<图名>.obj（z 向上），再用 tools/prepare_zodiac_figures.py 整理。
依赖与来源见 docs/sources/zodiac-heads-assets.md 第五节。
"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "third_party" / "TripoSR"))
import numpy as np, torch, rembg
from PIL import Image
from tsr.system import TSR
from tsr.utils import remove_background, resize_foreground

out_dir, *inputs = sys.argv[1:]
device = "mps" if torch.backends.mps.is_available() else "cpu"
t0 = time.time()
model = TSR.from_pretrained("stabilityai/TripoSR", config_name="config.yaml", weight_name="model.ckpt")
model.renderer.set_chunk_size(8192)
model.to(device)
print(f"[tsr] model loaded on {device} in {time.time()-t0:.0f}s", flush=True)
session = rembg.new_session()
for path in inputs:
    name = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    img = remove_background(Image.open(path).convert("RGB").resize((512, int(512 * Image.open(path).height / Image.open(path).width)), Image.LANCZOS), session)
    img = resize_foreground(img, 0.85)
    arr = np.array(img).astype(np.float32) / 255.0
    arr = arr[:, :, :3] * arr[:, :, 3:4] + (1 - arr[:, :, 3:4]) * 0.5
    Image.fromarray((arr * 255).astype(np.uint8)).save(f"{out_dir}/{name}_input.png")
    t1 = time.time()
    with torch.no_grad():
        codes = model([Image.fromarray((arr * 255).astype(np.uint8))], device=device)
    mesh = model.extract_mesh(codes, has_vertex_color=False, resolution=256)[0]
    mesh.export(f"{out_dir}/{name}.obj")
    print(f"[tsr] {name}: {len(mesh.vertices)} verts, {len(mesh.faces)} faces, {time.time()-t1:.0f}s", flush=True)
