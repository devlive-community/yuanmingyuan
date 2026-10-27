import { useCallback, useEffect, useRef, useState } from 'react';
import { loadModelBuffer } from '@model-loader';
import { DetailPanel } from './components/DetailPanel';
import { InfoCard, type LoadState } from './components/InfoCard';
import { Legend } from './components/Legend';
import { Sidebar } from './components/Sidebar';
import { manifest } from './data/manifest';
import { parseLabel } from './labels';
import type { Pick } from './types';
import { SceneViewer, type RenderMode } from './viewer/SceneViewer';

const { models, scenes, waters } = manifest;
const modelById = (id: string) => models.find((m) => m.id === id) ?? models[0];

export default function App() {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<SceneViewer | null>(null);
  const [current, setCurrent] = useState(() => modelById(location.hash.slice(1)));
  const currentRef = useRef(current);
  currentRef.current = current;
  const [pick, setPick] = useState<Pick | null>(null);
  const [load, setLoad] = useState<LoadState>({ loading: true });
  const [sideOpen, setSideOpen] = useState(false);
  const [mode, setMode] = useState<RenderMode>('realistic');

  // 目录选景：有「参考图效果」版本的景默认打开该版本（用户以参考图为目标）；信息卡上可切回史料复原
  const select = useCallback((id: string) => {
    setCurrent(models.find((m) => m.variantOf === id) ?? modelById(id));
    setSideOpen(false);
  }, []);
  const selectVersion = useCallback((id: string) => setCurrent(modelById(id)), []);

  // three.js 视口只创建一次；点选回调读取当前模型（ref）解析标签
  useEffect(() => {
    const viewer = new SceneViewer(containerRef.current!, (label) =>
      setPick(label ? parseLabel(label, currentRef.current.scene, scenes) : null),
    );
    viewerRef.current = viewer;
    return () => viewer.dispose();
  }, []);

  // 切换模型：按需解析 glb，换上后自适应相机
  useEffect(() => {
    let cancelled = false;
    setPick(null);
    setLoad({ loading: true });
    if (location.hash.slice(1) !== current.id) history.replaceState(null, '', `#${current.id}`);
    viewerRef.current!
      .parse(current.id, () => loadModelBuffer(current.id))
      .then((obj) => {
        if (cancelled) return;
        const size = viewerRef.current!.show(obj);
        setLoad({ loading: false, size: { x: size.x, y: size.y, z: size.z } });
      })
      .catch((e: unknown) => !cancelled && setLoad({ loading: false, error: String(e) }));
    return () => {
      cancelled = true;
    };
  }, [current]);

  // 选中建筑 → 高亮同栋；选中景内部件 → 高亮整景；选中水域 → 只高亮该块
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    if (!pick) return viewer.highlight(null);
    viewer.highlight((label) => {
      const k = parseLabel(label, current.scene, scenes);
      if (k.scene !== pick.scene) return false;
      if (pick.bkey) return k.bkey === pick.bkey;
      return scenes[pick.scene] ? true : k.part === pick.part;
    });
  }, [pick, current]);

  useEffect(() => {
    const onHash = () => {
      const id = location.hash.slice(1);
      if (id && id !== currentRef.current.id) select(id);
    };
    addEventListener('hashchange', onHash);
    return () => removeEventListener('hashchange', onHash);
  }, [select]);

  const buildingCount = current.scene ? Object.keys(scenes[current.scene].buildings).length : 0;
  const baseId = current.variantOf ?? current.id;
  const versions = models.filter((m) => m.id === baseId || m.variantOf === baseId);
  return (
    <>
      <div className="viewport" ref={containerRef} />
      <button className="menu" onClick={() => setSideOpen((v) => !v)}>
        ☰ 景区
      </button>
      <Sidebar models={models} scenes={scenes} currentId={baseId} open={sideOpen} onSelect={select} />
      <InfoCard
        key={current.id}
        model={current}
        versions={versions}
        onVersion={selectVersion}
        buildingCount={buildingCount}
        state={load}
        onView={(v) => viewerRef.current?.setView(v)}
        mode={mode}
        onMode={(m) => {
          setMode(m);
          setPick(null);
          viewerRef.current?.setMode(m);
        }}
      />
      {pick && (
        <DetailPanel
          pick={pick}
          scenes={scenes}
          waters={waters}
          inOverview={current.scene === null}
          onClose={() => setPick(null)}
          onGoto={select}
          onPick={setPick}
        />
      )}
      <Legend mode={mode} />
    </>
  );
}
