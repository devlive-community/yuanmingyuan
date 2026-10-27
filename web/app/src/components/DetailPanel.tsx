import { hasSpeculative, partLabel } from '../labels';
import type { BuildingMeta, Evidence, Pick, SceneMeta } from '../types';

interface Props {
  pick: Pick;
  scenes: Record<string, SceneMeta>;
  waters: Record<string, string>;
  inOverview: boolean; // 当前为总图：显示「进入此景」
  onClose: () => void;
  onGoto: (sceneId: string) => void;
  onPick: (pick: Pick) => void;
}

const CONFIDENCE = ['high', 'medium', 'low', 'placeholder'];

function Badge({ c }: { c: string }) {
  const k = CONFIDENCE.includes(c) ? c : 'low';
  return <span className={`badge b-${k}`}>{c || '未标'}</span>;
}

function EvidenceList({ items }: { items: Evidence[] }) {
  if (!items.length) return <div className="spec">未登记 evidence</div>;
  return (
    <>
      {items.map((e, i) => (
        <div className="ev" key={i}>
          <Badge c={e.confidence} />
          {e.source}
        </div>
      ))}
    </>
  );
}

const ENCLOSURE_ZH: Record<string, string> = {
  open: '敞（无墙无装修）',
  front: '前檐槅扇槛窗，三面墙',
  surround: '四面槛窗',
  gate: '门殿（板门）',
};

function BuildingView({ scene, b }: { scene: SceneMeta; b: BuildingMeta }) {
  const rows: Array<[string, string]> = [
    ['等级', `${b.grade} · ${b.module}`],
    ['间数', `面阔 ${b.bays} 间 × 进深 ${b.depth_bays} 间`],
    ['屋顶', b.roof + (b.stories > 1 ? ` · ${b.stories} 层` : '')],
    ['斗拱', b.brackets ?? (b.grade === '大式' ? '未建模（檐口落柱顶，S-002）' : '无（小式）')],
    ['围护', ENCLOSURE_ZH[b.enclosure] + (b.corridor === 'surround' ? ' · 周围廊' : '')],
    ['柱网', `${b.length_m} × ${b.width_m} m（柱中）`],
    ['檐柱高', `${b.column_m} m`],
    ['台基高', `${b.platform_chi} 尺`],
  ];
  return (
    <>
      <h2>{b.name}</h2>
      <div className="sub">
        {scene.name} · {b.role}
      </div>
      {hasSpeculative(b) && <div className="spec">含推测复原项（low / placeholder），见下方依据</div>}
      <table>
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k}>
              <td>{k}</td>
              <td>{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h3>史料依据</h3>
      <EvidenceList items={b.evidence} />
      {b.notes && (
        <>
          <h3>参数说明</h3>
          <pre className="notes">{b.notes}</pre>
        </>
      )}
      <div className="file">{b.file}</div>
    </>
  );
}

/** 右侧详情：点中建筑显示参数与 evidence；点中景内其他部件显示景说明；点中水域显示来源。 */
export function DetailPanel({ pick, scenes, waters, inOverview, onClose, onGoto, onPick }: Props) {
  const scene = scenes[pick.scene];
  const building = scene && pick.bkey ? scene.buildings[pick.bkey] : null;
  const gotoBtn = scene && inOverview && (
    <button className="linkbtn" onClick={() => onGoto(scene.id)}>
      进入「{scene.name}」单独查看 →
    </button>
  );

  let body;
  if (!scene) {
    body = (
      <>
        <h2>{waters[pick.scene] ?? partLabel(pick.scene)}</h2>
        <div className="sub">{partLabel(pick.part)}</div>
        <div className="spec">水域轮廓来自 OpenStreetMap（© OSM 贡献者，ODbL），非考古实测（S-028）。</div>
      </>
    );
  } else if (building) {
    body = (
      <>
        <BuildingView scene={scene} b={building} />
        {gotoBtn}
      </>
    );
  } else {
    const entries = Object.entries(scene.buildings);
    body = (
      <>
        <h2>{scene.name}</h2>
        <div className="sub">
          {pick.part && `${partLabel(pick.part)} · `}
          {scene.special ? '专属构建器（体量骨架）' : `${entries.length} 栋`}
        </div>
        {gotoBtn}
        {entries.length > 0 && (
          <>
            <h3>建筑</h3>
            <div className="blist">
              {entries.map(([key, b]) => (
                <button key={key} onClick={() => onPick({ scene: scene.id, bkey: key, part: '' })}>
                  {b.role} · {b.name}
                </button>
              ))}
            </div>
          </>
        )}
        {scene.notes && (
          <>
            <h3>景区说明</h3>
            <pre className="notes">{scene.notes}</pre>
          </>
        )}
        <div className="file">{scene.file}</div>
      </>
    );
  }

  return (
    <aside className="detail">
      <button className="close" aria-label="关闭" onClick={onClose}>
        ×
      </button>
      {body}
    </aside>
  );
}
