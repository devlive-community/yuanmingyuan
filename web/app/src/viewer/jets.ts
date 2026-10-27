import * as THREE from 'three';

/**
 * 喷泉水柱：由生成器导出的 `…/jet` 标记（两端点的细梁）生成。
 * - 落点与喷口水平分开：抛物线水柱（如生肖兽首、十犬喷鹿、狮子头）；
 * - 落点在喷口正上方：竖直喷泉，升至该高度后伞状散落（如喷水塔、池中喷泉）。
 *
 * 每道水柱由三层组成：连续的半透明水流管（沿流向滚动的条纹 + 边缘菲涅尔）、
 * 水流周围渐散的水珠、落点处溅起的水花。
 */

const SPRAY_PER_JET = 70;           // 沿流的水珠
const SPLASH_PER_JET = 36;          // 落点水花
const SPEED = 0.55;                 // 每秒走完水流全程的比例
const TUBE_SEGMENTS = 28;

interface Jet {
  a: THREE.Vector3;
  b: THREE.Vector3;
  vertical: boolean;
  arc: number;                      // 抛物线拱高（米）
}

/** 由标记网格读出喷口与落点（beam 顶点顺序：前 4 个在 p0 端、后 4 个在 p1 端）。 */
export function readJet(mesh: THREE.Mesh): Jet {
  const ends = mesh.userData.jet as number[] | undefined;            // 生成器写入的两端点（优先，不依赖顶点顺序）
  let a: THREE.Vector3, b: THREE.Vector3;
  if (ends?.length === 6) {
    // 端点为 glTF 场景坐标（绝对值）：不乘节点变换（meshopt 量化会给节点加缩放平移）
    a = new THREE.Vector3(ends[0], ends[1], ends[2]);
    b = new THREE.Vector3(ends[3], ends[4], ends[5]);
  } else {
    const pos = mesh.geometry.getAttribute('position') as THREE.BufferAttribute;
    const end = (from: number) => {
      const v = new THREE.Vector3();
      for (let i = from; i < from + 4; i++) v.add(new THREE.Vector3().fromBufferAttribute(pos, i));
      return v.multiplyScalar(0.25).applyMatrix4(mesh.matrixWorld);
    };
    a = end(0);
    b = end(4);
  }
  const horiz = Math.hypot(b.x - a.x, b.z - a.z);
  return { a, b, vertical: horiz < 0.05, arc: Math.max(0.25, horiz * 0.28) };
}

/** 水流路径上 u（0–1）处的位置。竖直喷泉只取上升段。 */
function pathPoint(jet: Jet, u: number, out: THREE.Vector3): THREE.Vector3 {
  const { a, b } = jet;
  if (jet.vertical) return out.set(a.x, a.y + (b.y - a.y) * u, a.z);
  return out.set(
    a.x + (b.x - a.x) * u,
    a.y + (b.y - a.y) * u + 4 * jet.arc * u * (1 - u),
    a.z + (b.z - a.z) * u,
  );
}

// ---------------------------------------------------------------------------
// 水流管
// ---------------------------------------------------------------------------

const streamVertex = /* glsl */ `
  varying vec2 vUv;
  varying vec3 vNormalV;
  varying vec3 vViewDir;
  void main() {
    vUv = uv;
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vNormalV = normalize(normalMatrix * normal);
    vViewDir = normalize(-mv.xyz);
    gl_Position = projectionMatrix * mv;
  }
`;

const streamFragment = /* glsl */ `
  uniform float time;
  varying vec2 vUv;
  varying vec3 vNormalV;
  varying vec3 vViewDir;
  float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
  float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
  }
  void main() {
    float flow = vUv.x * 26.0 - time * 5.0;
    float streak = noise(vec2(flow, vUv.y * 7.0)) * 0.65 + noise(vec2(flow * 2.3, vUv.y * 15.0)) * 0.35;
    float fres = 1.0 - abs(dot(normalize(vNormalV), normalize(vViewDir)));
    float alpha = 0.18 + 0.42 * streak + 0.4 * fres;
    alpha *= smoothstep(0.0, 0.04, vUv.x) * (1.0 - smoothstep(0.82, 1.0, vUv.x));
    vec3 col = mix(vec3(0.70, 0.82, 0.90), vec3(1.0), clamp(streak * 0.7 + fres * 0.5, 0.0, 1.0));
    gl_FragColor = vec4(col * 1.15, alpha * 0.85);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`;

function streamGeometry(jet: Jet): THREE.BufferGeometry {
  const pts: THREE.Vector3[] = [];
  for (let k = 0; k <= 16; k++) pts.push(pathPoint(jet, k / 16, new THREE.Vector3()));
  const curve = new THREE.CatmullRomCurve3(pts);
  const len = curve.getLength();
  const r0 = jet.vertical ? Math.min(0.09, 0.02 + len * 0.012) : Math.min(0.05, 0.018 + len * 0.006);
  const geo = new THREE.TubeGeometry(curve, TUBE_SEGMENTS, 1, 8, false);
  // 管径沿流向变化：抛物线水柱出口细、落下渐粗散；竖直水柱向上收细
  const pos = geo.getAttribute('position') as THREE.BufferAttribute;
  const uv = geo.getAttribute('uv') as THREE.BufferAttribute;
  const centre = new THREE.Vector3(), p = new THREE.Vector3();
  for (let i = 0; i < pos.count; i++) {
    const u = uv.getX(i);
    curve.getPointAt(Math.min(1, u), centre);
    p.fromBufferAttribute(pos, i).sub(centre);
    const r = jet.vertical ? r0 * (1.0 - 0.55 * u) : r0 * (1.0 + 1.6 * u);
    p.setLength(r).add(centre);
    pos.setXYZ(i, p.x, p.y, p.z);
  }
  geo.computeVertexNormals();
  return geo;
}

// ---------------------------------------------------------------------------
// 水珠与水花
// ---------------------------------------------------------------------------

function dropTexture(): THREE.Texture {
  const c = document.createElement('canvas');
  c.width = c.height = 64;
  const ctx = c.getContext('2d')!;
  const g = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
  g.addColorStop(0, 'rgba(255,255,255,1)');
  g.addColorStop(0.35, 'rgba(235,245,255,0.55)');
  g.addColorStop(1, 'rgba(235,245,255,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 64, 64);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

let sharedTexture: THREE.Texture | null = null;

/** 一个模型的全部水柱：水流管（一个合并网格）+ 水珠水花（一个 Points，逐帧更新）。 */
export class JetSystem {
  readonly object = new THREE.Group();
  private readonly points: THREE.Points;
  private readonly streamMaterial: THREE.ShaderMaterial;
  private readonly jets: Jet[];
  private readonly phase: Float32Array;
  private readonly angle: Float32Array;
  private readonly spread: Float32Array;
  private readonly tmp = new THREE.Vector3();

  constructor(jets: Jet[]) {
    this.jets = jets;
    this.streamMaterial = new THREE.ShaderMaterial({
      vertexShader: streamVertex,
      fragmentShader: streamFragment,
      uniforms: { time: { value: 0 } },
      transparent: true,
      depthWrite: false,
      side: THREE.DoubleSide,
    });
    for (const jet of jets) {
      const tube = new THREE.Mesh(streamGeometry(jet), this.streamMaterial);
      tube.renderOrder = 2;
      tube.raycast = () => {};                                     // 水流不参与点选
      this.object.add(tube);
    }

    const n = jets.length * (SPRAY_PER_JET + SPLASH_PER_JET);
    this.phase = new Float32Array(n).map(() => Math.random());
    this.angle = new Float32Array(n).map(() => Math.random() * Math.PI * 2);
    this.spread = new Float32Array(n).map(() => Math.random());
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 3), 3));
    sharedTexture ??= dropTexture();
    const mat = new THREE.PointsMaterial({
      map: sharedTexture,
      size: 0.2,
      sizeAttenuation: true,
      transparent: true,
      opacity: 0.75,
      depthWrite: false,
      color: 0xf2f8ff,
    });
    this.points = new THREE.Points(geo, mat);
    this.points.frustumCulled = false;
    this.points.renderOrder = 3;
    this.points.raycast = () => {};
    this.object.add(this.points);
    this.update(0);
  }

  update(t: number): void {
    this.streamMaterial.uniforms.time.value = t;
    const pos = this.points.geometry.getAttribute('position') as THREE.BufferAttribute;
    const arr = pos.array as Float32Array;
    const p = this.tmp;
    let i = 0;
    for (const jet of this.jets) {
      const { a, b } = jet;
      const h = b.y - a.y;
      for (let k = 0; k < SPRAY_PER_JET; k++, i++) {
        const u = (t * SPEED + this.phase[i]) % 1;
        const ca = Math.cos(this.angle[i]), sa = Math.sin(this.angle[i]);
        if (jet.vertical) {
          // 竖直喷泉：升至最高点后伞状下落，水平随时间散开
          const y = a.y + h * (1 - (2 * u - 1) ** 2);
          const r = h * 0.3 * u * (0.6 + 0.4 * this.spread[i]);
          arr[i * 3] = a.x + ca * r;
          arr[i * 3 + 1] = u > 0.5 ? Math.max(a.y - 0.05, y) : y;
          arr[i * 3 + 2] = a.z + sa * r;
        } else {
          // 沿抛物线，离喷口越远散得越开
          pathPoint(jet, u, p);
          const r = 0.03 + 0.22 * u * u * this.spread[i];
          arr[i * 3] = p.x + ca * r;
          arr[i * 3 + 1] = p.y + sa * r * 0.6;
          arr[i * 3 + 2] = p.z + sa * r;
        }
      }
      // 落点水花：短促上溅、向外散开（竖直喷泉落在喷口周围一圈）
      const land = jet.vertical ? a : b;
      const ring = jet.vertical ? h * 0.28 : 0;
      for (let k = 0; k < SPLASH_PER_JET; k++, i++) {
        const u = (t * 1.6 + this.phase[i]) % 1;
        const r = ring + (0.05 + 0.35 * this.spread[i]) * u;
        const up = (0.15 + 0.35 * this.spread[i]) * 4 * u * (1 - u);
        arr[i * 3] = land.x + Math.cos(this.angle[i]) * r;
        arr[i * 3 + 1] = land.y + up;
        arr[i * 3 + 2] = land.z + Math.sin(this.angle[i]) * r;
      }
    }
    pos.needsUpdate = true;
  }
}
