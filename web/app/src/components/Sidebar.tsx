import { useMemo, useState } from 'react';
import { GROUP_NAMES } from '../labels';
import type { ModelEntry, SceneMeta } from '../types';

interface Props {
  models: ModelEntry[];
  scenes: Record<string, SceneMeta>;
  currentId: string;
  open: boolean;
  onSelect: (id: string) => void;
}

/** 左侧模型列表：按分组列出总图 / 景区 / 样例，支持按名称筛选。 */
export function Sidebar({ models, scenes, currentId, open, onSelect }: Props) {
  const [filter, setFilter] = useState('');
  const groups = useMemo(() => {
    const out = new Map<ModelEntry['group'], ModelEntry[]>();
    for (const m of models) {
      if (m.variantOf) continue;                                    // 版本在信息卡上切换
      if (filter && !m.title.includes(filter)) continue;
      out.set(m.group, [...(out.get(m.group) ?? []), m]);
    }
    return [...out];
  }, [models, filter]);

  return (
    <nav className={`side${open ? ' open' : ''}`}>
      <header>
        <h1>圆明园数字复原</h1>
        <input
          className="search"
          type="search"
          placeholder="筛选景区…"
          value={filter}
          onChange={(e) => setFilter(e.target.value.trim())}
        />
      </header>
      <div className="list">
        {groups.map(([group, items]) => (
          <section key={group}>
            <div className="group">{GROUP_NAMES[group]}</div>
            {items.map((m) => {
              const n = m.scene ? Object.keys(scenes[m.scene].buildings).length : 0;
              return (
                <button
                  key={m.id}
                  className={`item${m.id === currentId ? ' active' : ''}`}
                  onClick={() => onSelect(m.id)}
                >
                  {m.title}
                  {n > 0 && <small>{n} 栋</small>}
                </button>
              );
            })}
          </section>
        ))}
        {groups.length === 0 && <div className="group">没有匹配的景区</div>}
      </div>
    </nav>
  );
}
