import * as THREE from 'three';

/**
 * 写实材质库：按网格标签末段（材质类 id）取 PBR 材质，纹理在浏览器内程序生成（离线可用）。
 *
 * 设色依据（见 docs/sources）：海晏堂墙身「粉红色灰」、屋面「孔雀绿琉璃瓦」、脊「黄琉璃」、
 * 汉白玉石作、法式铜窗、生肖铜首；中式殿宇灰筒瓦（正大光明谕旨）、朱红柱（油作通例）。
 * 纹理图案（瓦垄、石缝、窗棂、石纹）为程序生成的示意，非测绘。
 */

type Painter = (ctx: CanvasRenderingContext2D, size: number, rand: () => number) => void;

/** 实拍材质（Poly Haven CC0）：颜色 / 法线 / ARM（R 遮蔽、G 粗糙、B 金属）三图。 */
interface Photo {
  set: string;                      // 文件名前缀，如 'marble_01'
  tint?: string;                    // 按亮度重新着色到史料设色（保留实拍明暗与斑驳）
  strength?: number;                // 着色强度 0–1
  scale: number;                    // 一次重复覆盖的实际尺寸（米）
}

interface Spec {
  photo?: Photo;
  roughnessScale?: number;          // 乘到 ARM 粗糙度上（琉璃釉面取小值）
  clearcoat?: number;               // 釉面清漆
  color: string;
  roughness: number;
  metalness?: number;
  /** 纹理一次重复覆盖的实际尺寸（米） */
  scale?: number;
  albedo?: Painter;
  height?: Painter;
  normalStrength?: number;
  transparent?: number;
  water?: boolean;
}

const TEX_SIZE = 512;

function seeded(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

function canvas(size: number, paint: Painter, seed: number): HTMLCanvasElement {
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const ctx = c.getContext('2d')!;
  paint(ctx, size, seeded(seed));
  return c;
}

/** 平铺的值噪声（多倍频），用于抹灰、石材、草地的细微起伏。 */
function noiseLayer(ctx: CanvasRenderingContext2D, size: number, rand: () => number, base: number, amp: number) {
  const img = ctx.getImageData(0, 0, size, size);
  const grid = (cells: number) => {
    const g = Array.from({ length: cells * cells }, () => rand());
    return (x: number, y: number) => {
      const fx = (x / size) * cells, fy = (y / size) * cells;
      const x0 = Math.floor(fx), y0 = Math.floor(fy);
      const tx = fx - x0, ty = fy - y0;
      const at = (i: number, j: number) => g[((j % cells) * cells + (i % cells))];
      const a = at(x0, y0), b = at(x0 + 1, y0), c = at(x0, y0 + 1), d = at(x0 + 1, y0 + 1);
      const sx = tx * tx * (3 - 2 * tx), sy = ty * ty * (3 - 2 * ty);
      return a + (b - a) * sx + (c - a) * sy + (a - b - c + d) * sx * sy;
    };
  };
  const octaves = [grid(4), grid(8), grid(16), grid(64)];
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const n = octaves[0](x, y) * 0.45 + octaves[1](x, y) * 0.25 + octaves[2](x, y) * 0.18 + octaves[3](x, y) * 0.12;
      const v = Math.max(0, Math.min(255, base + (n - 0.5) * amp));
      const i = (y * size + x) * 4;
      img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
      img.data[i + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
}

// ---------------------------------------------------------------------------
// 图案（灰度高度图；albedo 由高度图着色得到）
// ---------------------------------------------------------------------------

const plaster: Painter = (ctx, size, rand) => noiseLayer(ctx, size, rand, 170, 70);

const marble: Painter = (ctx, size, rand) => {
  noiseLayer(ctx, size, rand, 205, 30);
  ctx.globalAlpha = 0.18;
  ctx.strokeStyle = '#5a5a5a';
  for (let k = 0; k < 9; k++) {                                   // 石纹
    ctx.lineWidth = 0.6 + rand() * 1.6;
    ctx.beginPath();
    let x = rand() * size, y = 0;
    ctx.moveTo(x, y);
    while (y < size) {
      x += (rand() - 0.5) * 40;
      y += 10 + rand() * 25;
      ctx.lineTo(x, y);
    }
    ctx.stroke();
  }
  ctx.globalAlpha = 1;
};

/** 琉璃筒瓦：沿 u 每 1/4 为一垄（筒瓦凸起 + 板瓦沟），沿 v 每 1/3 一道搭接缝。 */
const tiles: Painter = (ctx, size) => {
  const rows = 4;
  const img = ctx.createImageData(size, size);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const t = ((x / size) * rows) % 1;
      const tube = Math.max(0, Math.cos((t - 0.5) * Math.PI * 1.6));       // 筒瓦圆背
      const lap = ((y / size) * 3) % 1;
      const joint = lap < 0.05 ? 0.55 : 1;                                   // 搭接缝
      const v = (40 + 200 * tube) * joint;
      const i = (y * size + x) * 4;
      img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
      img.data[i + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
};

/** 鱼鳞瓦（远瀛观二层鱼鳞金瓦）。 */
const fishScale: Painter = (ctx, size) => {
  ctx.fillStyle = '#303030';
  ctx.fillRect(0, 0, size, size);
  const r = size / 8;
  for (let row = -1; row < 9; row++) {
    for (let col = -1; col < 9; col++) {
      const cx = col * 2 * r + (row % 2 ? r : 0), cy = row * r;
      const g = ctx.createRadialGradient(cx, cy, r * 0.2, cx, cy, r);
      g.addColorStop(0, '#f0f0f0');
      g.addColorStop(1, '#505050');
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI);
      ctx.fill();
    }
  }
};

/** 石板铺地 / 台明：3 × 3 块，块间灰缝，块内微起伏。 */
const slabs: Painter = (ctx, size, rand) => {
  noiseLayer(ctx, size, rand, 175, 40);
  const n = 3, cell = size / n;
  ctx.fillStyle = 'rgba(40,40,40,0.9)';
  for (let k = 0; k <= n; k++) {
    ctx.fillRect(0, k * cell - 2, size, 4);
    for (let j = 0; j < n; j++) {
      const off = (j % 2) * cell * 0.5;
      ctx.fillRect(((k * cell + off) % size) - 2, j * cell, 4, cell);
    }
  }
};

/** 青砖：一顺一丁的近似（每块约 30 × 7.5 cm，按 0.6 m 一个纹理周期）。 */
const bricks: Painter = (ctx, size, rand) => {
  noiseLayer(ctx, size, rand, 165, 50);
  const rows = 8, cols = 2, h = size / rows, w = size / cols;
  ctx.fillStyle = 'rgba(210,205,195,0.85)';                     // 白灰勾缝
  for (let j = 0; j < rows; j++) {
    ctx.fillRect(0, j * h - 1, size, 2);
    const off = (j % 2) * w * 0.5;
    for (let k = 0; k <= cols; k++) ctx.fillRect(((k * w + off) % size) - 1, j * h, 2, h);
  }
};

/** 法式铜窗：深色玻璃 + 铜窗棂（2 × 3 格）。高度图：窗棂高、玻璃低。 */
const windowPane: Painter = (ctx, size) => {
  ctx.fillStyle = '#202020';
  ctx.fillRect(0, 0, size, size);
  ctx.fillStyle = '#e0e0e0';
  const bar = size * 0.045;
  for (let k = 0; k <= 2; k++) ctx.fillRect(k * (size / 2) - bar / 2, 0, bar, size);
  for (let k = 0; k <= 3; k++) ctx.fillRect(0, k * (size / 3) - bar / 2, size, bar);
};

const grass: Painter = (ctx, size, rand) => {
  noiseLayer(ctx, size, rand, 140, 90);
  for (let k = 0; k < 4000; k++) {
    ctx.fillStyle = rand() > 0.5 ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)';
    ctx.fillRect(rand() * size, rand() * size, 1, 3);
  }
};

const ripples: Painter = (ctx, size, rand) => noiseLayer(ctx, size, rand, 128, 120);

// ---------------------------------------------------------------------------
// 材质类表（键 = 网格标签末段）
// ---------------------------------------------------------------------------

const SPECS: Record<string, Spec> = {
  // 西洋楼
  walls: { photo: { set: 'white_stucco_02', tint: '#dcbcb2', strength: 1, scale: 3 }, color: '#c48f82', roughness: 0.92, scale: 4, albedo: plaster, height: plaster, normalStrength: 0.6 },
  recess: { color: '#3b352e', roughness: 0.95, scale: 2, albedo: plaster },
  limestone: { photo: { set: 'marble_01', tint: '#e6d8bd', strength: 0.75, scale: 3 }, roughnessScale: 0.9, color: '#ddd0b6', roughness: 0.55, scale: 3, albedo: marble, height: marble, normalStrength: 0.4 },
  marble: { photo: { set: 'marble_01', tint: '#dcd8ce', strength: 0.85, scale: 2.4 }, roughnessScale: 0.8, color: '#cdc8bd', roughness: 0.42, scale: 2.5, albedo: marble, height: marble, normalStrength: 0.3 },
  glazed_roof: { photo: { set: 'clay_roof_tiles_02', tint: '#2f8a6f', strength: 1, scale: 1.6 }, roughnessScale: 0.35, clearcoat: 0.7, color: '#2f8a70', roughness: 0.22, scale: 1.2, albedo: tiles, height: tiles, normalStrength: 3.0 },
  glazed_ridge: { photo: { set: 'clay_roof_tiles_02', tint: '#d9a531', strength: 1, scale: 0.8 }, roughnessScale: 0.35, clearcoat: 0.7, color: '#d9a531', roughness: 0.25, scale: 1, albedo: plaster, height: plaster, normalStrength: 0.4 },
  gold_roof: { color: '#cfa64a', roughness: 0.35, metalness: 0.65, scale: 1.2, albedo: fishScale, height: fishScale, normalStrength: 2.0 },
  windows: { color: '#9a8a70', roughness: 0.15, metalness: 0.6, scale: 1.2, albedo: windowPane, height: windowPane, normalStrength: 2.0 },
  bronze: { color: '#8c6d3c', roughness: 0.32, metalness: 0.9, scale: 1, albedo: plaster },
  tin: { color: '#a5a9ad', roughness: 0.3, metalness: 0.9, scale: 2, albedo: plaster },
  paving: { photo: { set: 'rectangular_paving', tint: '#b2ab9e', strength: 0.75, scale: 2.5 }, color: '#a8a092', roughness: 0.85, scale: 2.4, albedo: slabs, height: slabs, normalStrength: 1.2 },
  water: { color: '#2f5f6a', roughness: 0.06, metalness: 0.0, scale: 6, height: ripples, normalStrength: 0.5, transparent: 0.93, water: true },
  cascade: { color: '#6a9aa4', roughness: 0.08, metalness: 0.0, scale: 2, height: ripples, normalStrength: 0.8, transparent: 0.88, water: true },
  // 中式殿宇
  platform: { photo: { set: 'marble_01', tint: '#c4beb1', strength: 0.8, scale: 2.4 }, color: '#beb7a8', roughness: 0.85, scale: 2.4, albedo: slabs, height: slabs, normalStrength: 1.2 },
  columns: { photo: { set: 'white_stucco_02', tint: '#6e140c', strength: 1, scale: 2 }, roughnessScale: 0.45, color: '#6e140c', roughness: 0.35, scale: 2, albedo: plaster, height: plaster, normalStrength: 0.2 },
  brackets: { color: '#2f625a', roughness: 0.7, scale: 1, albedo: plaster },
  beams: { color: '#2b5862', roughness: 0.7, scale: 1, albedo: plaster },
  red_wall: { photo: { set: 'white_stucco_02', tint: '#a4412f', strength: 1, scale: 3 }, color: '#9c3d2c', roughness: 0.9, scale: 4, albedo: plaster, height: plaster, normalStrength: 0.6 },
  wall_base: { color: '#8f8e88', roughness: 0.9, scale: 0.6, albedo: bricks, height: bricks, normalStrength: 1.2 },
  joinery: { photo: { set: 'white_stucco_02', tint: '#6a150d', strength: 1, scale: 2 }, roughnessScale: 0.45, color: '#6a150d', roughness: 0.4, scale: 2, albedo: plaster, height: plaster, normalStrength: 0.2 },
  paper: { color: '#e4dac2', roughness: 0.95, scale: 2, albedo: plaster },
  roof: { photo: { set: 'clay_roof_tiles_02', tint: '#5d6168', strength: 1, scale: 1.6 }, color: '#5a5e64', roughness: 0.65, scale: 1.2, albedo: tiles, height: tiles, normalStrength: 3.0 },
  island: { photo: { set: 'leafy_grass', scale: 4 }, color: '#857c62', roughness: 0.95, scale: 6, albedo: grass, height: grass, normalStrength: 0.8 },
  leaves: { color: '#4f7d32', roughness: 0.85 },
  foliage: { photo: { set: 'leafy_grass', tint: '#3d5c28', strength: 0.7, scale: 1.2 }, color: '#3f5e2c', roughness: 0.9, scale: 1.2, albedo: grass, height: grass, normalStrength: 2.5 },
  bark: { photo: { set: 'bark_willow', scale: 1.5 }, color: '#5b4632', roughness: 0.95, scale: 1, albedo: plaster, height: plaster, normalStrength: 1.5 },
  ground: { photo: { set: 'leafy_grass', tint: '#8fae55', strength: 0.6, scale: 4 }, color: '#7b8a52', roughness: 0.95, scale: 8, albedo: grass, height: grass, normalStrength: 0.6 },
};

const DEFAULT_SPEC: Spec = { color: '#a8a39a', roughness: 0.8, scale: 3, albedo: plaster };

function tintedTexture(paint: Painter, tint: THREE.Color, seed: number): THREE.CanvasTexture {
  const c = canvas(TEX_SIZE, paint, seed);
  const ctx = c.getContext('2d')!;
  const img = ctx.getImageData(0, 0, TEX_SIZE, TEX_SIZE);
  const r = tint.r * 255, g = tint.g * 255, b = tint.b * 255;
  for (let i = 0; i < img.data.length; i += 4) {
    const k = 0.55 + 0.45 * (img.data[i] / 255);                  // 高度 → 明暗
    img.data[i] = r * k; img.data[i + 1] = g * k; img.data[i + 2] = b * k;
  }
  ctx.putImageData(img, 0, 0);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.anisotropy = 8;
  return tex;
}

/** 由灰度高度图生成切线空间法线贴图（Sobel）。 */
function normalTexture(paint: Painter, strength: number, seed: number): THREE.CanvasTexture {
  const src = canvas(TEX_SIZE, paint, seed).getContext('2d')!.getImageData(0, 0, TEX_SIZE, TEX_SIZE).data;
  const out = document.createElement('canvas');
  out.width = out.height = TEX_SIZE;
  const ctx = out.getContext('2d')!;
  const img = ctx.createImageData(TEX_SIZE, TEX_SIZE);
  const h = (x: number, y: number) => src[(((y + TEX_SIZE) % TEX_SIZE) * TEX_SIZE + ((x + TEX_SIZE) % TEX_SIZE)) * 4] / 255;
  for (let y = 0; y < TEX_SIZE; y++) {
    for (let x = 0; x < TEX_SIZE; x++) {
      const dx = (h(x + 1, y) - h(x - 1, y)) * strength;
      const dy = (h(x, y + 1) - h(x, y - 1)) * strength;
      const len = Math.hypot(dx, dy, 1);
      const i = (y * TEX_SIZE + x) * 4;
      img.data[i] = ((-dx / len) * 0.5 + 0.5) * 255;
      img.data[i + 1] = ((dy / len) * 0.5 + 0.5) * 255;
      img.data[i + 2] = ((1 / len) * 0.5 + 0.5) * 255;
      img.data[i + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
  const tex = new THREE.CanvasTexture(out);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  return tex;
}

// ---------------------------------------------------------------------------
// 实拍纹理：加载、按亮度着色
// ---------------------------------------------------------------------------

export type AssetUrl = (file: string) => Promise<string>;

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`纹理加载失败 ${url.slice(0, 60)}`));
    img.src = url;
  });
}

/** 以亮度为明暗、把实拍颜色图重新着色到目标色（strength=1 完全换色，0 保持原色）。 */
function tintImage(img: HTMLImageElement, tint: string | undefined, strength: number): HTMLCanvasElement {
  const c = document.createElement('canvas');
  c.width = img.width;
  c.height = img.height;
  const ctx = c.getContext('2d')!;
  ctx.drawImage(img, 0, 0);
  if (!tint || strength <= 0) return c;
  const data = ctx.getImageData(0, 0, c.width, c.height);
  const d = data.data;
  let mean = 0;
  for (let i = 0; i < d.length; i += 4) mean += 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
  mean /= d.length / 4;
  const t = new THREE.Color(tint);
  const tr = t.r * 255, tg = t.g * 255, tb = t.b * 255;
  for (let i = 0; i < d.length; i += 4) {
    const k = (0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]) / mean;
    d[i] = d[i] + (Math.min(255, tr * k) - d[i]) * strength;
    d[i + 1] = d[i + 1] + (Math.min(255, tg * k) - d[i + 1]) * strength;
    d[i + 2] = d[i + 2] + (Math.min(255, tb * k) - d[i + 2]) * strength;
  }
  ctx.putImageData(data, 0, 0);
  return c;
}

function repeatTexture(src: HTMLCanvasElement | HTMLImageElement, srgb: boolean): THREE.Texture {
  const tex = new THREE.Texture(src);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.anisotropy = 8;
  if (srgb) tex.colorSpace = THREE.SRGBColorSpace;
  tex.needsUpdate = true;
  return tex;
}

interface PhotoMaps {
  map: THREE.Texture;
  normalMap: THREE.Texture;
  arm: THREE.Texture;
}

async function loadPhoto(photo: Photo, url: AssetUrl): Promise<PhotoMaps> {
  const [diff, nor, arm] = await Promise.all(
    (['diff', 'nor', 'arm'] as const).map(async (k) => loadImage(await url(`${photo.set}_${k}.webp`))),
  );
  return {
    map: repeatTexture(tintImage(diff, photo.tint, photo.strength ?? 1), true),
    normalMap: repeatTexture(nor, false),
    arm: repeatTexture(arm, false),
  };
}

export interface MaterialLibrary {
  get(key: string): { material: THREE.MeshStandardMaterial; scale: number };
  /** 示意模式用的纯色材质（烘焙模型的 glb 材质是光照图，不能当示意色）。 */
  schematic(key: string): THREE.MeshStandardMaterial;
  /** 水面法线贴图（逐帧平移做波纹） */
  waterNormals: THREE.Texture[];
}

/** 建材质库：先并行加载全部实拍纹理（失败的退回程序纹理），之后 get() 同步取用。 */
export async function createMaterialLibrary(url: AssetUrl): Promise<MaterialLibrary> {
  const photos = new Map<string, PhotoMaps>();
  await Promise.all(
    Object.entries(SPECS).map(async ([key, spec]) => {
      if (!spec.photo) return;
      try {
        photos.set(key, await loadPhoto(spec.photo, url));
      } catch (e) {
        console.warn(`实拍材质 ${key} 不可用，改用程序纹理`, e);
      }
    }),
  );
  const cache = new Map<string, { material: THREE.MeshStandardMaterial; scale: number }>();
  const waterNormals: THREE.Texture[] = [];
  let seed = 1;
  return {
    waterNormals,
    schematic(key: string) {
      const spec = SPECS[key] ?? DEFAULT_SPEC;
      return new THREE.MeshStandardMaterial({ color: spec.color, roughness: 0.8, side: THREE.DoubleSide });
    },
    get(key: string) {
      const hit = cache.get(key);
      if (hit) return hit;
      const spec = SPECS[key] ?? DEFAULT_SPEC;
      const color = new THREE.Color(spec.color);
      const photo = photos.get(key);
      if (photo && spec.photo) {
        const mat = new THREE.MeshPhysicalMaterial({
          map: photo.map,
          normalMap: photo.normalMap,
          aoMap: photo.arm,
          roughnessMap: photo.arm,
          roughness: spec.roughnessScale ?? 1,
          metalness: spec.metalness ?? 0,             // 实拍材质均为非金属；不用 ARM 的 B 通道
          clearcoat: spec.clearcoat ?? 0,
          clearcoatRoughness: 0.08,
          side: THREE.DoubleSide,
        });
        const entry = { material: mat as THREE.MeshStandardMaterial, scale: spec.photo.scale };
        cache.set(key, entry);
        return entry;
      }
      const mat = new THREE.MeshStandardMaterial({
        color: spec.albedo ? 0xffffff : color,
        roughness: spec.roughness,
        metalness: spec.metalness ?? 0,
        side: THREE.DoubleSide,
      });
      if (spec.albedo) mat.map = tintedTexture(spec.albedo, color, seed++);
      if (spec.height) {
        mat.normalMap = normalTexture(spec.height, spec.normalStrength ?? 1, seed++);
        if (spec.water) waterNormals.push(mat.normalMap);
      }
      if (spec.transparent !== undefined) {
        mat.transparent = true;
        mat.opacity = spec.transparent;
      }
      const entry = { material: mat, scale: spec.scale ?? 3 };
      cache.set(key, entry);
      return entry;
    },
  };
}

/** 网格标签末段 → 材质类 id。 */
export const materialKey = (label: string): string => label.split('/').pop() ?? '';

/**
 * 逐面平面投影 UV（单位：米 / scale）：u 沿水平切向、v 沿面内上坡向。
 * 屋面瓦垄因此顺坡、窗棂与石缝在立面上横平竖直；需非索引几何（每面独立顶点）。
 */
export function planarUVs(geometry: THREE.BufferGeometry, scale: number, matrix?: THREE.Matrix4): THREE.BufferGeometry {
  const g = geometry.index ? geometry.toNonIndexed() : geometry;
  const pos = g.getAttribute('position') as THREE.BufferAttribute;
  const uv = new Float32Array(pos.count * 2);
  const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
  const n = new THREE.Vector3(), t = new THREE.Vector3(), bt = new THREE.Vector3();
  const up = new THREE.Vector3(0, 1, 0);
  for (let i = 0; i < pos.count; i += 3) {
    a.fromBufferAttribute(pos, i);
    b.fromBufferAttribute(pos, i + 1);
    c.fromBufferAttribute(pos, i + 2);
    if (matrix) {                                    // 量化压缩的网格带节点变换：按世界坐标（米）投影
      a.applyMatrix4(matrix);
      b.applyMatrix4(matrix);
      c.applyMatrix4(matrix);
    }
    n.subVectors(c, b).cross(t.subVectors(a, b)).normalize();
    t.crossVectors(up, n);
    if (t.lengthSq() < 1e-6) t.set(1, 0, 0);
    t.normalize();
    bt.crossVectors(n, t).normalize();
    for (let k = 0; k < 3; k++) {
      const p = k === 0 ? a : k === 1 ? b : c;
      uv[(i + k) * 2] = p.dot(t) / scale;
      uv[(i + k) * 2 + 1] = p.dot(bt) / scale;
    }
  }
  g.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  smoothNormals(g, CREASE_DEG);
  return g;
}

/** 折角阈值：相邻面夹角小于它时共享平滑法线（旋转体、卷涡、团块圆润），大于它保持硬边（墙角、台阶）。 */
const CREASE_DEG = 40;

/**
 * 按折角平滑法线（非索引几何）。位置相同（容差取包围球半径的 1e-5）的顶点中，
 * 只累加与本面法线夹角小于阈值的面法线。不依赖顶点顺序与 UV 接缝。
 */
export function smoothNormals(g: THREE.BufferGeometry, creaseDeg: number): void {
  const pos = g.getAttribute('position') as THREE.BufferAttribute;
  const n = pos.count;
  g.computeBoundingSphere();
  const eps = Math.max(g.boundingSphere!.radius * 1e-5, 1e-7);
  const p = new Float64Array(n * 3);
  for (let i = 0; i < n; i++) {
    p[i * 3] = pos.getX(i); p[i * 3 + 1] = pos.getY(i); p[i * 3 + 2] = pos.getZ(i);
  }
  const faceN = new Float64Array(n);                               // 每面一个法线（3 分量 = n / 3 面 × 3）
  for (let f = 0; f < n / 3; f++) {
    const a = f * 9;
    const ux = p[a + 3] - p[a], uy = p[a + 4] - p[a + 1], uz = p[a + 5] - p[a + 2];
    const vx = p[a + 6] - p[a], vy = p[a + 7] - p[a + 1], vz = p[a + 8] - p[a + 2];
    let nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
    const len = Math.hypot(nx, ny, nz) || 1;
    nx /= len; ny /= len; nz /= len;
    faceN[f * 3] = nx; faceN[f * 3 + 1] = ny; faceN[f * 3 + 2] = nz;
  }
  const groups = new Map<string, number[]>();
  const key = (i: number) => `${Math.round(p[i * 3] / eps)},${Math.round(p[i * 3 + 1] / eps)},${Math.round(p[i * 3 + 2] / eps)}`;
  for (let i = 0; i < n; i++) {
    const k = key(i);
    const list = groups.get(k);
    if (list) list.push(i);
    else groups.set(k, [i]);
  }
  const cos = Math.cos(THREE.MathUtils.degToRad(creaseDeg));
  const out = new Float32Array(n * 3);
  for (const list of groups.values()) {
    for (const i of list) {
      const fi = Math.floor(i / 3) * 3;
      let sx = 0, sy = 0, sz = 0;
      for (const j of list) {
        const fj = Math.floor(j / 3) * 3;
        const d = faceN[fi] * faceN[fj] + faceN[fi + 1] * faceN[fj + 1] + faceN[fi + 2] * faceN[fj + 2];
        if (d >= cos) { sx += faceN[fj]; sy += faceN[fj + 1]; sz += faceN[fj + 2]; }
      }
      const len = Math.hypot(sx, sy, sz) || 1;
      out[i * 3] = sx / len; out[i * 3 + 1] = sy / len; out[i * 3 + 2] = sz / len;
    }
  }
  g.setAttribute('normal', new THREE.BufferAttribute(out, 3));
}

export const GRASS_SPEC_KEY = 'ground';
