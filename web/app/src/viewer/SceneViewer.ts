import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { HDRLoader } from 'three/addons/loaders/HDRLoader.js';
import { Sky } from 'three/addons/objects/Sky.js';
import { loadAssetUrl } from '@model-loader';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { GTAOPass } from 'three/addons/postprocessing/GTAOPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { JetSystem, readJet } from './jets';
import { leafGeometry, leafMaterial } from './leaves';
import { SkyDome } from './skyDome';
import { createMaterialLibrary, GRASS_SPEC_KEY, materialKey, planarUVs, type MaterialLibrary } from './materials';

const BG = 0x10151c;

/** 视角预设：铜版画四面 + 俯视。场景 +X 东、+Y 北 → three 为 (x, z=−y)。 */
export type ViewName = 'west' | 'south' | 'east' | 'north' | 'top' | 'eye';
const VIEW_DIRS: Record<ViewName, [number, number, number]> = {
  west: [-1, 0.32, 0],
  east: [1, 0.32, 0],
  south: [0, 0.32, 1],
  north: [0, 0.32, -1],
  top: [0.001, 1, 0.001],
  eye: [-1, 0.02, 0],                                              // 人视：无机位标记时自西平视
};

/** 写实：PBR 材质 + 天空 + 日照阴影；示意：按构件占位色（便于区分构件）。 */
export type RenderMode = 'realistic' | 'schematic';

const HIGHLIGHT = 0x5a4310;
const CLICK_SLOP_PX = 5;
const METAL_ENV_INTENSITY = 1.1;                                   // 金属反射强度（单独挂环境图时）
const SUN_DIR = new THREE.Vector3(-0.55, 0.62, 0.56).normalize();   // 默认西南来光；有 HDRI 时对齐其太阳
const SHADOW_MAX_RADIUS_M = 400;
const MAX_PIXEL_RATIO = 1.5;
const LIGHTMAP_DECODE = 2.0;                                        // 与 bake_scene.py 的 LIGHTMAP_SCALE=0.5 对应
// 开阔地面的天空辐照度：取烘焙光照图中无遮挡水平面的典型值（sRGB 8 位编码，同光照图）
const OPEN_SKY_LIGHTMAP = (() => {
  const t = new THREE.DataTexture(new Uint8Array([66, 110, 200, 255]), 1, 1);
  t.colorSpace = THREE.SRGBColorSpace;
  t.channel = 1;
  t.needsUpdate = true;
  return t;
})();                                        // Retina 下限制像素比，画质与帧率折中                                      // 超过此尺度（总图）不投影

/** 网格的完整英文标签：导出时写在 glTF node extras.label（three 会净化 name 中的 '/'）。 */
export const labelOf = (o: THREE.Object3D): string => String(o.userData.label ?? o.name);

interface MeshMaterials {
  schematic: THREE.Material;
  realistic: THREE.MeshStandardMaterial;
}

function configureSky(sky: Sky): void {
  const u = sky.material.uniforms;
  u.turbidity.value = 4;
  u.rayleigh.value = 1.2;
  u.mieCoefficient.value = 0.004;
  u.mieDirectionalG.value = 0.8;
  u.sunPosition.value.copy(SUN_DIR);
}

/**
 * three.js 视口：渲染循环、相机自适应、点选与高亮、写实/示意两种渲染。
 * React 只持有实例并调用方法，不参与逐帧渲染。
 */
export class SceneViewer {
  private readonly renderer: THREE.WebGLRenderer;
  private readonly scene = new THREE.Scene();
  private readonly camera = new THREE.PerspectiveCamera(45, 1, 0.05, 2000);
  private readonly controls: OrbitControls;
  private readonly grid = new THREE.GridHelper(80, 80, 0x2c3a4a, 0x1c2733);
  private readonly sun = new THREE.DirectionalLight(0xfff1dc, 1.5);
  private readonly hemi = new THREE.HemisphereLight(0xbfd4e6, 0x2a2e26, 1.1);
  private readonly sky = new Sky();
  private ground: THREE.Mesh | null = null;
  private materials!: MaterialLibrary;
  private hdrSky: THREE.Texture | null = null;
  private readonly sunDir = SUN_DIR.clone();
  private readonly dome = new SkyDome(SUN_DIR);                    // 写实模式背景：蓝天积云（光照仍用 HDRI）
  /** 材质纹理与 HDRI 天空加载完成；parse 前须等待。 */
  readonly ready: Promise<void>;
  private readonly raycaster = new THREE.Raycaster();
  private readonly resizeObserver: ResizeObserver;
  private readonly loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
  private readonly cache = new Map<string, THREE.Object3D>();
  private readonly clock = new THREE.Clock();
  private envMap: THREE.Texture;
  private readonly composer: EffectComposer;
  private readonly ao: GTAOPass;
  private mode: RenderMode = 'realistic';
  private model: THREE.Object3D | null = null;
  private center = new THREE.Vector3();
  private radius = 1;
  private highlighted: THREE.MeshStandardMaterial[] = [];
  private pointerDown: [number, number] | null = null;

  constructor(
    private readonly container: HTMLElement,
    private readonly onPick: (label: string | null) => void,
  ) {
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, MAX_PIXEL_RATIO));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFShadowMap;
    this.renderer.shadowMap.autoUpdate = false;                    // 建筑静止：阴影只在换模型 / 换模式时重算
    container.appendChild(this.renderer.domElement);

    this.scene.fog = new THREE.Fog(BG, 90, 420);
    this.sun.shadow.mapSize.set(2048, 2048);
    this.sun.shadow.radius = 2;
    this.sun.shadow.bias = -0.0004;
    this.sun.shadow.normalBias = 0.03;
    this.scene.add(this.hemi, this.sun, this.sun.target, this.grid);

    // 天空（Preetham 物理天空）+ 由同一天空生成的环境反射
    configureSky(this.sky);
    this.scene.add(this.sky, this.dome);
    const skyForEnv = new Sky();
    configureSky(skyForEnv);
    skyForEnv.scale.setScalar(1000);
    const pmrem = new THREE.PMREMGenerator(this.renderer);
    this.envMap = pmrem.fromScene(new THREE.Scene().add(skyForEnv) as THREE.Scene).texture;
    pmrem.dispose();


    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.maxPolarAngle = Math.PI / 2 - 0.03; // 不允许转到地面以下
    // 平移：右键拖动，或按住 Shift / ⌘ / Ctrl 再左键拖动（OrbitControls 内置）；方向键平移画面
    // 缩放朝鼠标所指处推进，放大后目标不会跑出画面
    this.controls.zoomToCursor = true;
    this.controls.screenSpacePanning = true;
    this.controls.keyPanSpeed = 25;
    this.controls.listenToKeyEvents(window);

    const el = this.renderer.domElement;
    el.addEventListener('pointerdown', this.handlePointerDown);
    el.addEventListener('pointerup', this.handlePointerUp);
    // 后期：环境光遮蔽（GTAO），使券洞、檐下、线脚交接处有接触阴影；写实模式启用
    this.composer = new EffectComposer(
      this.renderer,
      new THREE.WebGLRenderTarget(1, 1, { samples: 2, type: THREE.HalfFloatType }),   // 后期链内保留 MSAA
    );
    this.composer.addPass(new RenderPass(this.scene, this.camera));
    this.ao = new GTAOPass(this.scene, this.camera, 1, 1);
    this.ao.blendIntensity = 0.85;
    this.composer.addPass(this.ao);
    this.composer.addPass(new OutputPass());

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(container);
    this.resize();
    this.applyEnvironment();
    this.ready = this.init();
    this.renderer.setAnimationLoop(() => {
      const dt = this.clock.getDelta();
      for (const tex of this.materials?.waterNormals ?? []) tex.offset.x += dt * 0.02;  // 水面微波
      (this.model?.userData.jets as JetSystem | undefined)?.update(this.clock.elapsedTime);
      this.controls.update();
      this.updateNear();
      this.dome.update(this.camera, this.clock.elapsedTime);
      // 屏幕空间 AO 只在写实模式、模型无烘焙光照、且设备跑得动时开启；否则直接渲染（最省）
      if (this.mode === 'realistic' && this.useScreenAO()) this.composer.render();
      else this.renderer.render(this.scene, this.camera);
      this.adaptQuality(dt);
    });
  }

  private baseNear = 0.1;

  /** 近裁剪面随镜头离注视点的距离调整：拉远时取大（深度精度高、远处不闪），贴近细看时缩小（不裁掉近物）。 */
  private updateNear(): void {
    const d = this.camera.position.distanceTo(this.controls.target);
    const near = Math.min(this.baseNear, Math.max(0.02, d / 60));
    if (Math.abs(near - this.camera.near) > near * 0.05) {
      this.camera.near = near;
      this.camera.updateProjectionMatrix();
    }
  }

  /** 加载实拍材质与 HDRI 天空，建地面。 */
  private async init(): Promise<void> {
    this.materials = await createMaterialLibrary(loadAssetUrl);
    const grass = this.materials.get(GRASS_SPEC_KEY);
    const groundGeo = planarUVs(new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2), grass.scale);
    groundGeo.setAttribute('uv1', groundGeo.getAttribute('uv'));
    const groundMat = grass.material.clone();
    // 草地只比铺地、池底低几厘米：远看时深度精度不足会与之「深度冲突」闪烁，故把草地在深度上整体推后
    groundMat.polygonOffset = true;
    groundMat.polygonOffsetFactor = 4;
    groundMat.polygonOffsetUnits = 8;
    this.ground = new THREE.Mesh(groundGeo, groundMat);
    this.ground.receiveShadow = true;
    this.scene.add(this.ground);
    try {
      const hdr = await new HDRLoader().setDataType(THREE.FloatType).loadAsync(await loadAssetUrl('sky.hdr'));
      hdr.mapping = THREE.EquirectangularReflectionMapping;
      // 把 HDRI 绕竖轴旋转，使其太阳落在西南（照亮西向正立面）；高度角沿用 HDRI 实测
      const hdrSun = brightestDirection(hdr);
      const yaw = Math.atan2(hdrSun.z, hdrSun.x) - Math.atan2(SUN_DIR.z, SUN_DIR.x);
      this.scene.backgroundRotation.set(0, yaw, 0);
      this.scene.environmentRotation.set(0, yaw, 0);
      const flat = Math.hypot(SUN_DIR.x, SUN_DIR.z);
      this.sunDir.set((SUN_DIR.x / flat) * Math.hypot(hdrSun.x, hdrSun.z), hdrSun.y,
                      (SUN_DIR.z / flat) * Math.hypot(hdrSun.x, hdrSun.z)).normalize();
      const pmrem = new THREE.PMREMGenerator(this.renderer);
      this.envMap = pmrem.fromEquirectangular(hdr).texture;
      pmrem.dispose();
      this.hdrSky = hdr;
      this.dome.material.uniforms.sunDir.value.copy(this.sunDir);
    } catch (e) {
      console.warn('HDRI 天空不可用，改用程序天空', e);
    }
    this.applyEnvironment();
    if (this.model) this.fit(this.model);
  }

  /** 解析 glb（按模型 id 缓存），并为每个网格准备写实 / 示意两套材质。 */
  async parse(id: string, buffer: () => Promise<ArrayBuffer>): Promise<THREE.Object3D> {
    await this.ready;
    const hit = this.cache.get(id);
    if (hit) return hit;
    const gltf = await this.loader.parseAsync(await buffer(), '');
    gltf.scene.updateMatrixWorld(true);
    gltf.scene.traverse((o) => {                                     // 预扫：是否为烘焙模型（含光照图）
      if (o instanceof THREE.Mesh && (o.material as THREE.MeshStandardMaterial).map) gltf.scene.userData.baked = true;
    });
    const jets: ReturnType<typeof readJet>[] = [];
    gltf.scene.traverse((o) => {
      if (!(o instanceof THREE.Mesh)) return;
      const key = materialKey(labelOf(o));
      if (key === 'jet') {                                          // 喷水标记：隐藏，改由粒子水柱表现
        jets.push(readJet(o));
        o.visible = false;
        return;
      }
      if (key === 'viewpoint') {                                    // 人视机位标记：眼 → 注视点（glTF 场景坐标）
        const v = o.userData.viewpoint as number[] | undefined;
        if (v?.length === 6) gltf.scene.userData.viewpoint = v;
        o.visible = false;
        return;
      }
      if (key === 'leaves') {                                       // 叶片卡树冠：透明叶簇 + 球形法线，不烘焙
        o.geometry = leafGeometry(o.geometry);
        o.userData.materials = { schematic: this.materials.schematic(key), realistic: leafMaterial() } as MeshMaterials;
        o.castShadow = true;
        o.receiveShadow = true;
        return;
      }
      const lib = this.materials.get(key);
      // 烘焙模型：glb 材质的颜色贴图即该网格的光照图，其 UV（TEXCOORD_0）挪到第二通道
      const glbMat = o.material as THREE.MeshStandardMaterial;
      const lightMap = glbMat.map && o.geometry.getAttribute('uv') ? glbMat.map : null;
      if (lightMap) {
        o.geometry.setAttribute('uv1', o.geometry.getAttribute('uv'));
        o.geometry.deleteAttribute('uv');
        lightMap.channel = 1;
      }
      o.geometry = planarUVs(o.geometry, lib.scale, o.matrixWorld);
      const realistic = lib.material.clone();
      if (lightMap) {
        realistic.lightMap = lightMap;
        realistic.lightMapIntensity = LIGHTMAP_DECODE;
      }
      // 金属（铜像、锡板、金瓦、铜窗）的颜色几乎全来自反射：单独挂环境图，不受烘焙景整体压低的环境强度影响
      if (realistic.metalness >= 0.5 && this.envMap) {
        realistic.envMap = this.envMap;
        realistic.envMapRotation.copy(this.scene.environmentRotation);
        realistic.envMapIntensity = METAL_ENV_INTENSITY;
      }
      const schematic = gltf.scene.userData.baked || !glbMat.color ? this.materials.schematic(key) : o.material;
      const meshMaterials: MeshMaterials = { schematic, realistic };
      o.userData.materials = meshMaterials;                         // 逐网格克隆，高亮互不影响
      o.castShadow = !lib.material.transparent;
      o.receiveShadow = true;
    });
    if (jets.length) {
      const system = new JetSystem(jets);
      gltf.scene.add(system.object);
      gltf.scene.userData.jets = system;
    }
    this.cache.set(id, gltf.scene);
    return gltf.scene;
  }

  /** 换上模型并让相机框住它，返回外包尺寸（米，three 为 Y-up）。 */
  show(obj: THREE.Object3D): THREE.Vector3 {
    this.highlight(null);
    if (this.model) this.scene.remove(this.model);
    this.model = obj;
    this.scene.add(obj);
    this.applyMaterials();
    const size = this.fit(obj);
    this.renderer.shadowMap.needsUpdate = true;
    return size;
  }

  // ---- 自适应画质：按帧时调节（先关屏幕空间 AO，再降分辨率；富余时逐级恢复）----
  private frameAvg = 1 / 60;
  private qualityLevel = 0;                                         // 0 全开 / 1 关 AO / 2 降分辨率
  private qualityCooldown = 0;

  private useScreenAO(): boolean {
    return this.qualityLevel === 0 && !this.model?.userData.baked;
  }

  private adaptQuality(dt: number): void {
    this.frameAvg += (Math.min(dt, 0.2) - this.frameAvg) * 0.05;
    this.qualityCooldown -= dt;
    if (this.qualityCooldown > 0) return;
    if (this.frameAvg > 1 / 30 && this.qualityLevel < 2) {
      this.setQuality(this.qualityLevel + 1);
    } else if (this.frameAvg < 1 / 55 && this.qualityLevel > 0) {
      this.setQuality(this.qualityLevel - 1);
    }
  }

  private setQuality(level: number): void {
    this.qualityLevel = level;
    this.qualityCooldown = 2.0;
    const ratio = level >= 2 ? 1 : Math.min(window.devicePixelRatio, MAX_PIXEL_RATIO);
    if (ratio !== this.renderer.getPixelRatio()) {
      this.renderer.setPixelRatio(ratio);
      this.composer.setPixelRatio(ratio);
      this.resize();
    }
  }

  /** 切换写实 / 示意渲染。 */
  setMode(mode: RenderMode): void {
    this.highlight(null);
    this.mode = mode;
    this.applyEnvironment();
    this.applyMaterials();
  }

  /** 切换到预设视角（看向模型中心，距离同自适应）。 */
  setView(view: ViewName): void {
    const vp = this.model?.userData.viewpoint as number[] | undefined;
    if (view === 'eye' && vp) {
      this.camera.position.set(vp[0], vp[1], vp[2]);
      this.controls.target.set(vp[3], vp[4], vp[5]);
      this.controls.update();
      return;
    }
    const halfFov = THREE.MathUtils.degToRad(this.camera.fov / 2);
    const dist = (this.radius / Math.sin(halfFov)) * 0.75;
    const dir = new THREE.Vector3(...VIEW_DIRS[view]).normalize();
    this.camera.position.copy(this.center).addScaledVector(dir, dist);
    this.controls.target.copy(this.center);
    this.controls.update();
  }

  /** 高亮满足条件的网格；传 null 清除。 */
  highlight(pred: ((label: string) => boolean) | null): void {
    this.highlighted.forEach((m) => m.emissive.setHex(0x000000));
    this.highlighted = [];
    if (!this.model || !pred) return;
    this.model.traverse((o) => {
      if (o instanceof THREE.Mesh && o.material instanceof THREE.MeshStandardMaterial && pred(labelOf(o))) {
        o.material.emissive.setHex(HIGHLIGHT);
        this.highlighted.push(o.material);
      }
    });
  }

  dispose(): void {
    this.renderer.setAnimationLoop(null);
    this.resizeObserver.disconnect();
    this.controls.stopListenToKeyEvents();
    this.controls.dispose();
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }

  private applyMaterials(): void {
    this.model?.traverse((o) => {
      const mats = o.userData.materials as MeshMaterials | undefined;
      if (o instanceof THREE.Mesh && mats) o.material = this.mode === 'realistic' ? mats.realistic : mats.schematic;
    });
  }

  private applyEnvironment(): void {
    const real = this.mode === 'realistic';
    this.sky.visible = false;                                         // Preetham 天空只用于生成后备环境图
    this.dome.visible = real;
    if (this.ground) this.ground.visible = real;
    this.grid.visible = !real;
    this.scene.background = real ? null : new THREE.Color(BG);
    this.scene.environment = real ? this.envMap : null;
    (this.scene.fog as THREE.Fog).color.set(real ? this.dome.horizon : new THREE.Color(BG));
    this.renderer.toneMapping = real ? THREE.ACESFilmicToneMapping : THREE.NoToneMapping;
    // HDRI 取自海滩（下半球偏沙黄）：只用其天空做反射与少量环境光，补以中性天光 + 草地反射光
    const hdr = real && !!this.hdrSky;
    const baked = real && !!this.model?.userData.baked;             // 光照图已含天空光：关掉补光，环境只留反射
    this.renderer.toneMappingExposure = real ? (hdr ? (this.model?.userData.baked ? 1.05 : 0.95) : 0.78) : 1.0;
    this.sun.intensity = real ? (hdr ? 3.0 : 2.8) : 1.5;
    this.hemi.intensity = real ? (baked ? 0.0 : hdr ? 0.55 : 0.9) : 1.1;
    // 烘焙景中地面不在光照图内：给它与烘焙一致的「开阔天空」辐照度（常量光照图），免得草地只受直射而发暗
    if (this.ground) {
      const gm = this.ground.material as THREE.MeshStandardMaterial;
      gm.lightMap = baked ? OPEN_SKY_LIGHTMAP : null;
      gm.lightMapIntensity = LIGHTMAP_DECODE;
      gm.needsUpdate = true;
    }
    this.scene.environmentIntensity = baked ? 0.3 : hdr ? 0.45 : 1.0;
    this.hemi.color.setHex(real ? 0xdfe8f2 : 0xbfd4e6);
    this.hemi.groundColor.setHex(real ? (hdr ? 0x6f7d52 : 0x8a7f6a) : 0x2a2e26);
    this.sun.castShadow = real && this.radius < SHADOW_MAX_RADIUS_M;
    this.renderer.shadowMap.needsUpdate = true;
  }

  private fit(obj: THREE.Object3D): THREE.Vector3 {
    const box = new THREE.Box3().setFromObject(obj, true);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    const sphere = box.getBoundingSphere(new THREE.Sphere());
    this.center.copy(center);
    this.radius = sphere.radius;
    const radius = Math.max(size.x, size.y, size.z) || 1;
    this.grid.position.set(center.x, 0, center.z);
    this.grid.scale.setScalar(Math.max(1, (radius * 2.4) / 80));
    // 按包围球取距离；扁平模型（总图）俯角更陡，避免斜视下整片缩成一条
    const halfFov = THREE.MathUtils.degToRad(this.camera.fov / 2);
    const dist = (sphere.radius / Math.sin(halfFov)) * 0.8;
    const flat = size.y < 0.05 * Math.max(size.x, size.z);
    const dir = new THREE.Vector3(0.55, flat ? 1.5 : 0.62, 0.8).normalize();
    this.camera.position.copy(center).addScaledVector(dir, dist);
    this.camera.near = Math.max(dist / 200, 0.05);                      // 近裁剪面不宜过近：深度精度主要由它决定
    this.baseNear = this.camera.near;
    this.camera.far = dist * 60;
    this.camera.updateProjectionMatrix();
    const fog = this.scene.fog as THREE.Fog;
    fog.near = radius * 2.0; // 雾距随模型尺寸自适应
    fog.far = radius * (this.mode === 'realistic' ? 9.0 : 14.0);
    this.controls.target.copy(center);
    this.controls.update();

    // 天空、地面、日照阴影随模型尺度
    this.sky.scale.setScalar(this.camera.far * 0.9);
    this.dome.scale.setScalar(this.camera.far * 0.5);
    this.ground?.scale.setScalar(Math.max(radius * 400, 20000));      // 铺到地平线，远处由雾融入天空
    this.ground?.position.set(center.x, -0.08, center.z);
    this.sun.position.copy(center).addScaledVector(this.sunDir, sphere.radius * 3);
    this.sun.target.position.copy(center);
    const cam = this.sun.shadow.camera;
    cam.left = cam.bottom = -sphere.radius * 1.1;
    cam.right = cam.top = sphere.radius * 1.1;
    cam.near = sphere.radius * 0.5;
    cam.far = sphere.radius * 6;
    cam.updateProjectionMatrix();
    this.applyEnvironment();
    return size;
  }

  private resize(): void {
    const { clientWidth: w, clientHeight: h } = this.container;
    if (!w || !h) return;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
    this.composer.setSize(w, h);
  }

  private readonly handlePointerDown = (e: PointerEvent): void => {
    this.pointerDown = [e.clientX, e.clientY];
  };

  private readonly handlePointerUp = (e: PointerEvent): void => {
    const down = this.pointerDown;
    this.pointerDown = null;
    // 拖动（旋转/平移）不算点选
    if (!down || !this.model || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > CLICK_SLOP_PX) return;
    const rect = this.renderer.domElement.getBoundingClientRect();
    const ndc = new THREE.Vector2(
      ((e.clientX - rect.left) / rect.width) * 2 - 1,
      -((e.clientY - rect.top) / rect.height) * 2 + 1,
    );
    this.raycaster.setFromCamera(ndc, this.camera);
    const hit = this.raycaster
      .intersectObject(this.model, true)
      .find((h) => h.object instanceof THREE.Mesh && h.object.visible);
    this.onPick(hit ? labelOf(hit.object) : null);
  };
}

/** HDRI 中最亮像素的方向（即太阳方向），用于对齐直射光与阴影。 */
function brightestDirection(hdr: THREE.DataTexture): THREE.Vector3 {
  const { width: w, height: h, data } = hdr.image as { width: number; height: number; data: Float32Array };
  let best = -1, bx = 0, by = 0;
  const step = data.length / (w * h);
  for (let y = 0; y < h / 2; y++) {                       // 只看上半球
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * step;
      const lum = 0.2126 * data[i] + 0.7152 * data[i + 1] + 0.0722 * data[i + 2];
      if (lum > best) { best = lum; bx = x; by = y; }
    }
  }
  // HDRLoader 首行为图像顶部（flipY）：v = 1 − 行/高；经度 u 对应 three 等距柱状映射
  const u = (bx + 0.5) / w, v = 1 - (by + 0.5) / h;
  const lat = (v - 0.5) * Math.PI;
  const lon = (u - 0.5) * 2 * Math.PI;
  const dir = new THREE.Vector3(Math.cos(lat) * Math.cos(lon), Math.sin(lat), Math.cos(lat) * Math.sin(lon));
  if (dir.y < 0.25) dir.y = 0.25;                         // 太阳过低时抬高，保证阴影可读
  return dir.normalize();
}
