import * as THREE from 'three';

/**
 * 写实模式的天空背景：天顶深蓝 → 地平线浅蓝的渐变 + 程序积云（fbm 噪声投影到云层平面，缓慢漂移）。
 * 只作背景；场景光照与反射仍用 HDRI 环境图。球体每帧跟随相机，不参与雾与深度。
 */

const vertexShader = /* glsl */ `
  varying vec3 vDir;
  void main() {
    vDir = normalize(position);
    vec4 p = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    gl_Position = p.xyww;                                        // 置于远平面
  }
`;

const fragmentShader = /* glsl */ `
  uniform vec3 zenith;
  uniform vec3 horizon;
  uniform vec3 sunDir;
  uniform float time;
  varying vec3 vDir;

  float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
  float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
  }
  float fbm(vec2 p) {
    float v = 0.0, a = 0.5;
    for (int k = 0; k < 6; k++) { v += a * noise(p); p = p * 2.03 + vec2(1.7, 9.2); a *= 0.5; }
    return v;
  }

  void main() {
    vec3 d = normalize(vDir);
    float h = max(d.y, 0.0);
    vec3 sky = mix(horizon, zenith, pow(h, 0.55));
    float s = max(dot(d, normalize(sunDir)), 0.0);
    sky += vec3(1.0, 0.92, 0.75) * (pow(s, 600.0) * 8.0 + pow(s, 12.0) * 0.12);   // 日轮与日晕
    if (d.y > 0.0) {
      vec2 uv = d.xz / (d.y + 0.12) * 1.6 + vec2(time * 0.004, time * 0.0015);   // 云层平面投影
      float n = fbm(uv);
      float cover = smoothstep(0.52, 0.78, n);                   // 积云：成团、边缘柔和
      float shade = fbm(uv * 1.8 + 3.1);
      vec3 cloud = mix(vec3(0.72, 0.76, 0.82), vec3(1.05, 1.03, 1.0), smoothstep(0.35, 0.75, shade));
      float fade = smoothstep(0.02, 0.18, d.y);                   // 近地平线处淡出
      sky = mix(sky, cloud, cover * fade * 0.95);
    } else {
      sky = horizon;
    }
    gl_FragColor = vec4(sky, 1.0);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`;

export class SkyDome extends THREE.Mesh<THREE.SphereGeometry, THREE.ShaderMaterial> {
  constructor(sunDir: THREE.Vector3) {
    const material = new THREE.ShaderMaterial({
      vertexShader,
      fragmentShader,
      uniforms: {
        zenith: { value: new THREE.Color('#2a63b8') },
        horizon: { value: new THREE.Color('#c6dcef') },
        sunDir: { value: sunDir.clone() },
        time: { value: 0 },
      },
      side: THREE.BackSide,
      depthWrite: false,
      fog: false,
      toneMapped: true,
    });
    super(new THREE.SphereGeometry(1, 48, 24), material);
    this.frustumCulled = false;
    this.renderOrder = -1;
  }

  /** 每帧：跟随相机、推进云的漂移。 */
  update(camera: THREE.Camera, t: number): void {
    this.position.copy(camera.position);
    this.material.uniforms.time.value = t;
  }

  /** 地平线色（供雾色对齐）。 */
  get horizon(): THREE.Color {
    return this.material.uniforms.horizon.value as THREE.Color;
  }
}
