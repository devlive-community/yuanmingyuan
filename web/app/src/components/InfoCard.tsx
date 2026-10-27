import { useState } from 'react';
import type { ModelEntry } from '../types';
import type { RenderMode, ViewName } from '../viewer/SceneViewer';

const VIEWS: Array<[ViewName, string]> = [
  ['eye', '人视'], ['west', '西'], ['south', '南'], ['east', '东'], ['north', '北'], ['top', '俯'],
];

export interface LoadState {
  loading: boolean;
  error?: string;
  size?: { x: number; y: number; z: number };
}

interface Props {
  model: ModelEntry;
  versions: ModelEntry[]; // 同一景的各版本（只有一版时不显示切换）
  onVersion: (id: string) => void;
  buildingCount: number;
  state: LoadState;
  onView: (view: ViewName) => void;
  mode: RenderMode;
  onMode: (mode: RenderMode) => void;
}

/** 顶部信息卡：当前模型名、规模、外包尺寸与可展开的景区说明（YAML 头注释）。 */
export function InfoCard({ model, versions, onVersion, buildingCount, state, onView, mode, onMode }: Props) {
  const [notesOpen, setNotesOpen] = useState(false);
  // 专属构建器景（如海晏堂）没有参数化建筑，不显示「0 栋」
  const count = !model.scene ? `${model.sceneCount} 景` : buildingCount > 0 ? `${buildingCount} 栋` : '专属构建器';
  const { size } = state;
  return (
    <div className="top">
      <div className="card">
        <div className="title">
          {model.title}
          {model.group === 'samples' && <span className="tag">样例 · 非复原</span>}
          {model.variantOf && <span className="tag">参考图效果 · 非史料复原</span>}
        </div>
        {versions.length > 1 && (
          <div className="views">
            版本
            {versions.map((v) => (
              <button key={v.id} className={v.id === model.id ? 'on' : ''} onClick={() => onVersion(v.id)}>
                {v.variantOf ? '参考图效果' : '史料复原'}
              </button>
            ))}
          </div>
        )}
        <div className="stats">
          {state.loading
            ? '加载中…'
            : size && `${count} · 外包 ${size.x.toFixed(1)} × ${size.z.toFixed(1)} × ${size.y.toFixed(1)} m`}
        </div>
        <div className="views">
          视角
          {VIEWS.map(([v, label]) => (
            <button key={v} onClick={() => onView(v)}>
              {label}
            </button>
          ))}
          <span className="sep" />
          {(['realistic', 'schematic'] as const).map((m) => (
            <button key={m} className={mode === m ? 'on' : ''} onClick={() => onMode(m)}>
              {m === 'realistic' ? '写实' : '示意'}
            </button>
          ))}
        </div>
        <button className="notes-btn" onClick={() => setNotesOpen((v) => !v)}>
          {notesOpen ? '收起景区说明 ▴' : '展开景区说明 ▾'}
        </button>
        {notesOpen && <pre className="notes">{model.notes || '（无说明）'}</pre>}
        {state.error && <div className="err">加载失败：{state.error}</div>}
      </div>
    </div>
  );
}
