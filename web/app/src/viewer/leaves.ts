import * as THREE from 'three';

/**
 * 叶片卡树冠（生成器 `…/leaves`）：每张方形面片贴一簇透明叶片纹理（alphaTest 镂空），
 * 法线取「自树冠中心向外、略偏上」，使整团树冠像球体一样受光（游戏植被的常用做法）。
 */

let leafTexture: THREE.Texture | null = null;

/** 叶簇纹理：圆形区域内随机分布的椭圆叶片，多种绿色，背景透明。 */
function paintLeaves(): THREE.Texture {
  const size = 256;
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const ctx = c.getContext('2d')!;
  let s = 7;
  const rand = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  const greens = ['#3f6b2a', '#4f7d32', '#5e8c3a', '#35602a', '#6f9a44', '#2f5424'];
  for (let k = 0; k < 170; k++) {
    const a = rand() * Math.PI * 2;
    const r = Math.sqrt(rand()) * size * 0.4;
    const x = size / 2 + Math.cos(a) * r, y = size / 2 + Math.sin(a) * r;
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(rand() * Math.PI * 2);
    ctx.fillStyle = greens[Math.floor(rand() * greens.length)];
    ctx.beginPath();
    ctx.ellipse(0, 0, size * (0.035 + rand() * 0.02), size * (0.017 + rand() * 0.008), 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  return tex;
}

export function leafMaterial(): THREE.MeshStandardMaterial {
  leafTexture ??= paintLeaves();
  return new THREE.MeshStandardMaterial({
    map: leafTexture,
    alphaTest: 0.5,
    side: THREE.DoubleSide,
    roughness: 0.85,
    color: 0xffffff,
  });
}

/**
 * 叶片卡几何：逐三角形求 UV 与法线。
 * 方形卡被三角化成两个沿对角线的三角形；以最长边（对角线）中点为卡心、
 * 对角线方向与「卡心 → 第三点」为两轴，叶簇纹理（圆形、近似中心对称）因此每卡完整一簇，
 * 与顶点顺序无关（压缩 / 烘焙会重排顶点）。
 */
export function leafGeometry(geometry: THREE.BufferGeometry): THREE.BufferGeometry {
  const g = geometry.index ? geometry.toNonIndexed() : geometry;
  const pos = g.getAttribute('position') as THREE.BufferAttribute;
  const uv = new Float32Array(pos.count * 2);
  const normal = new Float32Array(pos.count * 3);
  g.computeBoundingSphere();
  const sphere = g.boundingSphere!;
  const centre = sphere.center.clone().add(new THREE.Vector3(0, -0.35 * sphere.radius, 0));   // 偏下：顶部更亮
  const p = [new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3()];
  const m = new THREE.Vector3(), e1 = new THREE.Vector3(), e2 = new THREE.Vector3(), d = new THREE.Vector3();
  for (let i = 0; i < pos.count; i += 3) {
    for (let k = 0; k < 3; k++) p[k].fromBufferAttribute(pos, i + k);
    const lens = [p[0].distanceTo(p[1]), p[1].distanceTo(p[2]), p[2].distanceTo(p[0])];
    const j = lens.indexOf(Math.max(...lens));                  // 对角线 = 最长边 (j, j+1)
    const a = p[j], b = p[(j + 1) % 3], c = p[(j + 2) % 3];
    m.addVectors(a, b).multiplyScalar(0.5);
    const half = a.distanceTo(b) / 2 || 1;
    e1.subVectors(b, a).normalize();
    e2.subVectors(c, m).normalize();
    for (let k = 0; k < 3; k++) {
      d.subVectors(p[k], m);
      uv[(i + k) * 2] = 0.5 + d.dot(e1) / (2 * half);
      uv[(i + k) * 2 + 1] = 0.5 + d.dot(e2) / (2 * half);
      d.subVectors(p[k], centre).normalize();
      normal.set([d.x, d.y, d.z], (i + k) * 3);
    }
  }
  g.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  g.setAttribute('normal', new THREE.BufferAttribute(normal, 3));
  return g;
}
