# web · 浏览器查看

## 查看器（React）

`web/app/` 为 React 19 + Vite + TypeScript + three.js 工程：左侧景区列表切换模型
（三园总图 / 24 景 / 生成器样例），点击建筑在右侧查看参数、史料依据与置信度
（low / placeholder 项标为「推测复原」）。

```bash
cd web/app
npm install          # 首次
npm run data         # 由 YAML 生成模型与 manifest（tools/export_web_data.py）
npm run dev          # 开发：浏览器打开终端提示的 localhost 地址
npm run build:offline  # 打成单个 HTML，复制为仓库根目录「圆明园全景-打开这个.html」
```

也可在仓库根目录一步完成数据导出 + 离线单文件构建：`python3 tools/build_final_page.py`。

**命名约定**：生成器与导出数据中的网格标签一律为英文 id，形如
`{景 id}/{建筑 key}/{构件}`（例 `zhengda_guangming/peidian_wuying_2/roof`，建筑 key 为
建筑 YAML 的 id，同景重复引用加 `_2`）；完整标签存于 glTF node `extras.label`。
中文名称只在页面渲染时查表（`web/app/src/labels.ts`）或取自 YAML 数据值。

## 单独导出 glb（不经网页）

```bash
python3 blender/export/export_glb.py --config data/buildings/zhengda_guangming.yaml --out build/zhengda_guangming.glb
python3 blender/export/export_glb.py --scene  data/scenes/zhengda_guangming.yaml    --out build/zhengda_guangming_scene.glb
python3 blender/export/export_glb.py --garden data/gardens/sanyuan_osm.yaml         --out build/sanyuan_osm.glb
```

## 地形数据（OSM，© OpenStreetMap 贡献者，ODbL）

`data/terrain/water_polygons.json` 由 OSM 区域地图 XML 提取，重建方法：

```bash
# 1) 抓取区域地图（约 5.8 MB）
curl -o build/osm_map.xml "https://api.openstreetmap.org/api/0.6/map?bbox=116.290,40.000,116.330,40.025"
# 2) 提取水域多边形（含水体关系外环）
python3 tools/osm_to_terrain.py build/osm_map.xml data/terrain/water_polygons.json
```

水域轮廓为真实测绘（志愿者数据，示意精度）；摆位与水面高程为示意（S-028）。

以上均无需 Blender（纯 Python glTF 写出器，见 `blender/generator/gltf.py`）；
Blender 路径（`blender/generator/assemble.py`）保留，两条路径共用同一几何层。

## 文件

| 路径 | 说明 |
|---|---|
| `app/src/viewer/SceneViewer.ts` | three.js 视口：渲染、相机自适应、点选与高亮 |
| `app/src/components/` | 侧栏、信息卡、详情面板、图例（React） |
| `app/src/labels.ts` | 英文标签 → 中文显示名 |
| `app/src/generated/` | 导出数据（`npm run data` 生成，勿手改） |
| `../圆明园全景-打开这个.html` | 离线单文件（`npm run build:offline` 生成，勿手改） |

## 声明

页面中的材质为**占位颜色**（台基灰 / 柱朱红 / 屋顶灰瓦），仅用于区分构件；
屋顶灰瓦有谕旨依据，其余非史料依据。正式材质待彩画与瓦色史料核定后实现。

## 照片级效果图（Blender Cycles）

需安装 Blender（4.x / 5.x）。几何与网页同一份 glb，材质在 Blender 中按材质类重建：

```bash
python3 blender/export/export_glb.py --scene data/scenes/haiyantang.yaml --out build/haiyantang.glb
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P blender/render/cycles_render.py -- \
    --glb build/haiyantang.glb --out build/renders/haiyantang_west.png --view west --samples 128
```

视角：`west`（铜版画西面视点）/ `south` / `east` / `aerial`。M2 GPU（Metal）1920×1080、128 采样约 1 分钟。

## 实拍材质（Poly Haven，CC0）

`assets/polyhaven/` 存放原始 2k 纹理与 HDRI（CC0 公有领域，来源与许可见该目录 LICENSE.txt）。
`npm run data` 会把它们缩为 1k WebP 打进网页；写实模式下按亮度重新着色到史料设色（见 S-013）。

## 烘焙光照（游戏式实时画质）

`tools/export_web_data.py` 对 `BAKED_SCENES`（当前：海晏堂）自动执行：
Blender 倒角（单段斜切，只倒直角硬边）→ Cycles 烘焙天空光照图（每对象一张，约 24 px/m，含天空遮蔽与反弹）
→ `gltf-transform meshopt` 压缩。结果按内容哈希缓存在 `build/baked/`，几何或烘焙脚本不变则不重烘。
浏览器端：光照图作为 lightMap（第二套 UV），太阳直射与阴影实时计算；烘焙景关闭屏幕空间 AO（更快）。
需 Blender（默认 `/Applications/Blender.app`，可用环境变量 `BLENDER` 指定）；缺失时退回未烘焙模型。

性能（M2，Retina 1600×1000，2026-10-22 实测）：海晏堂 80–110 fps，三园总图约 70 fps。
自适应画质：帧时超 33 ms 先关屏幕空间 AO、再降像素比，富余时恢复。
