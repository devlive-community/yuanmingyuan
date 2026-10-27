# 十二生肖兽首：写实模型的来源与接入

生肖兽首默认用程序雕塑（`blender/generator/sculpt.py`），只能做到风格化示意。
写实兽首走「照片生成 3D」：用博物馆 / 新闻照片在图生 3D 工具里生成模型，经脚本整理后自动替换雕塑兽首
（史料复原版与参考图效果版同时生效）。

## 一、要准备的照片

| 生肖 | 原件现状 | 照片建议 |
|---|---|---|
| 现存七首：牛 ox、虎 tiger、猴 monkey、猪 pig、马 horse、鼠 rat、兔 rabbit | 已回归（保利艺术博物馆 / 圆明园馆藏 / 国家博物馆） | 原件正面或 3/4 侧面、背景干净、光线均匀；一首一张即可，有正面 + 侧面两张更好 |
| 龙 dragon、蛇 snake、羊 goat、鸡 rooster、狗 dog | 下落不明 | 只能用复制品或复原像的照片，生成结果属推测复原 |

## 二、生成模型

1. 在图生 3D 工具（如 Tripo、Meshy、混元 3D）里上传照片，生成**带几何细节**的模型（材质无所谓，场景里统一为铜）。
2. 导出为 GLB（OBJ、FBX、STL 也可）。
3. 按生肖英文名命名，放进 `assets/zodiac_heads/raw/`：

   ```
   assets/zodiac_heads/raw/ox.glb
   assets/zodiac_heads/raw/tiger.glb
   assets/zodiac_heads/raw/monkey.glb
   …
   ```

   英文名：rat 鼠、ox 牛、tiger 虎、rabbit 兔、dragon 龙、snake 蛇、horse 马、goat 羊、monkey 猴、rooster 鸡、dog 狗、pig 猪。
   不必一次凑齐，缺的继续用雕塑兽首。

## 三、整理并接入

```bash
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P tools/prepare_zodiac_heads.py
python3 tools/build_final_page.py
```

脚本会合并网格、减到约 12000 个三角面、对齐底面中心、统一高度，写出 `assets/zodiac_heads/<生肖>.obj`；
生成器检测到这些文件就用它们代替雕塑兽首，喷水口取头部中高度最靠前的点（吻端）。

朝向：默认模型「面朝前」（glTF 的 +Z，图生 3D 工具通常如此）。若某首朝向不对，
在 `assets/zodiac_heads/raw/orientation.json` 里补转，例如 `{"ox": {"yaw": 90}}`（度，绕竖轴），再跑一次脚本。

## 四、来源与许可记录

每接入一首，在下表登记照片来源与生成工具（照片与工具的使用条款由使用者确认）：

| 生肖 | 照片来源 | 生成工具 | 日期 | 可信度 |
|---|---|---|---|---|
| 马 | [Bronze Horse Head Grand Lisboa 02.jpg](https://commons.wikimedia.org/wiki/File:Bronze_Horse_Head_Grand_Lisboa_02.jpg) | CC BY-SA 4.0 | 未用于生成 | 2026-10-27 | — |
| 羊 | [Bronze goat head.JPG](https://commons.wikimedia.org/wiki/File:Bronze_goat_head.JPG) | CC BY 3.0 | TripoSR（本机） | 2026-10-27 | low（复制品照片） |
| 牛 | [Bronze ox head.JPG](https://commons.wikimedia.org/wiki/File:Bronze_ox_head.JPG) | CC BY 3.0 | TripoSR（本机） | 2026-10-27 | low（复制品照片） |
| 鼠 | [VM Yuanmingyuan Haiyantang Mouse 4427.jpg](https://commons.wikimedia.org/wiki/File:VM_Yuanmingyuan_Haiyantang_Mouse_4427.jpg) | CC BY-SA 3.0 | TripoSR（本机） | 2026-10-27 | low（复制品照片） |
| （参照）遗址整像复制品 | [VM Yuanmingyuan Haiyantang bronze figure replicas 4440.jpg](https://commons.wikimedia.org/wiki/File:VM_Yuanmingyuan_Haiyantang_bronze_figure_replicas_4440.jpg) | CC BY-SA 3.0 | 未用于生成 | 2026-10-27 | — |
| （参照）遗址兽首展示 | [VM Yuanmingyuan Haiyantang bronze heads 4431.jpg](https://commons.wikimedia.org/wiki/File:VM_Yuanmingyuan_Haiyantang_bronze_heads_4431.jpg) | CC BY-SA 3.0 | 未用于生成 | 2026-10-27 | — |
| 狗 | [圆明园狗首.JPG](https://commons.wikimedia.org/wiki/File:圆明园狗首.JPG) | CC BY-SA 3.0 | TripoSR（本机） | 2026-10-27 | low（复制品照片） |
| 猪 | [圆明园猪首.JPG](https://commons.wikimedia.org/wiki/File:圆明园猪首.JPG) | CC BY-SA 3.0 | TripoSR（本机） | 2026-10-27 | low（复制品照片） |
| 猴 | [圆明园猴首.JPG](https://commons.wikimedia.org/wiki/File:圆明园猴首.JPG) | CC BY-SA 3.0 | TripoSR（本机） | 2026-10-27 | low（复制品照片） |
| 虎 | [圆明园虎首.JPG](https://commons.wikimedia.org/wiki/File:圆明园虎首.JPG) | CC BY-SA 3.0 | TripoSR（本机） | 2026-10-27 | low（复制品照片） |
| 龙 | [圆明园龙首.JPG](https://commons.wikimedia.org/wiki/File:圆明园龙首.JPG) | CC BY-SA 3.0 | TripoSR（本机） | 2026-10-27 | low（复制品照片） |

可信度约定：现存原件照片生成为 medium（形体来自原件，细部为工具推断）；复制品 / 复原像照片生成为 low。

## 五、参考图效果版：整尊铜像（2026-10-27）

参考图效果版的十二生肖改用**整尊铜像模型**（`assets/zodiac_figures/`），按用户提供的参考效果图生成：

- 从参考图截取四尊较清晰的铜像（`assets/zodiac_figures/raw/ref_*.png`），在本机用 TripoSR
  （VAST-AI-Research/TripoSR，MIT 许可；权重 stabilityai/TripoSR）逐尊单图生成 3D（`raw/ref_*.obj`）。
  本地补丁：`third_party/TripoSR/tsr/models/isosurface.py` 以 scikit-image 代替需编译的 torchmcubes。
- `tools/prepare_zodiac_figures.py` 减面（每尊约 2.4 万面）、平滑重建噪点、以吻部定正面、高度归一。
- 十二个位置轮流使用四种造型；参考图中铜像兽首多为鼠、犬一类，**不能区分十二生肖**，属参考图效果，非史料。
- 背面与被遮挡部分由模型推断补全。

重新生成：

```bash
.venv/bin/python -I tools/tsr_generate.py assets/zodiac_figures/raw assets/zodiac_figures/raw/ref_*.png
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P tools/prepare_zodiac_figures.py
python3 tools/build_final_page.py
```

## 六、照片生成兽首（2026-10-27）

八首（鼠牛虎龙羊猴狗猪）由上表维基共享资源照片截取头部（`assets/zodiac_heads/photos/<生肖>.png`），
本机 TripoSR 生成（`raw/<生肖>.obj`），`tools/prepare_zodiac_heads.py` 轻度平滑、截去展台支杆、减面后接入
（`raw/orientation.json` 标 `"source": "triposr"`：z 向上、正面朝 +x）。照片多为遗址展陈的复制品，形制与原件一致；
马首照片隔玻璃罩侧拍过于模糊未用，兔、蛇、鸡三首未找到合适照片，仍为雕塑兽首。
照片作者与许可以表中链接页为准；CC BY-SA 照片生成的模型按同许可署名共享。

另：`ref_figures_4440` 显示遗址展示的整像复制品为**袍服盘坐像、手持器物**，与史料版坐像形制相符。

## 七、史料版坐像身躯（2026-10-27）

史料版生肖像身躯改用遗址展示整像复制品照片（`photos/ref_figures_4440.jpg`，Vmenkov，CC BY-SA 3.0）生成：
截取盘坐执杖的猴像与捧瓶的羊像（`photos/seated_*.png`），本机 TripoSR 生成（`assets/zodiac_seated/raw/`），
`tools/prepare_zodiac_figures.py -- assets/zodiac_seated/raw assets/zodiac_seated` 整理；侧拍照片自动判向不可靠，
朝向在 `raw/orientation.json` 手动指定。生成器去掉原头（颈部 72% 通高以上），装上各生肖照片兽首，两种身躯轮换。
身躯按史料仍为石雕（复制品为全铜），盘坐、执物的姿态以复制品为据（low–medium）。

## 八、参考图效果版：十二生肖逐尊铜像（2026-10-27，取代第五节）

用户提供十二生肖逐尊特写图（`assets/zodiac_figures/raw/closeups_12.png`，4×3 宫格，AI 生成效果图，非史料）。
每格截取铜像、遮去生肖字签，按颜色去掉口中水柱（偏蓝亮白且非铜色的像素，外扩 4 像素），
本机 TripoSR 逐尊生成（`raw/<生肖>.obj`），`tools/prepare_zodiac_figures.py` 整理（同一拍摄角度，统一正面方位 45°，
见 `raw/orientation.json`）。生成器按文件名把各尊放到对应生肖位（`sculpt.load_figure_named`）。
早先由总览参考图截取的五种造型移至 `assets/zodiac_figures/archive_ref6/`（不再使用）。
铜像造型（盘坐、长袍、手持如意 / 宝珠 / 权杖等）属参考效果图，与史料版（遗址复制品盘坐像）分别对待。

## 九、本机 TripoSR 环境（重新生成模型时）

`.venv/`、`third_party/` 不入库，按下列步骤重建：

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python torch omegaconf==2.3.0 einops==0.7.0 transformers==4.35.0 \
    trimesh==4.0.5 "rembg[cpu]" huggingface-hub pillow numpy scikit-image
git clone https://github.com/VAST-AI-Research/TripoSR third_party/TripoSR   # 本项目基于 107cefd
git -C third_party/TripoSR apply ../../tools/patches/triposr-isosurface-skimage.patch
```

首次运行会下载权重（约 1.7 GB）；之后可加 `HF_HUB_OFFLINE=1` 离线运行。
`assets/*/raw/*.obj` 为生成中间件，不入库：用同目录截图跑 `tools/tsr_generate.py` 重新生成。
