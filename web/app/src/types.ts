/** manifest.json 的结构（由 tools/export_web_data.py 生成）。键一律为英文 id。 */

export type ModelGroup = 'overview' | 'scenes' | 'samples';

export interface Evidence {
  source: string;
  confidence: string; // high / medium / low / placeholder
}

export interface BuildingMeta {
  id: string;
  role: string;
  name: string;
  grade: string;
  module: string;
  bays: number;
  depth_bays: number;
  roof: string;
  brackets: string | null; // 斗拱（bracket_set），无则 null
  enclosure: string;       // 围护：open / front / surround / gate（carpentry.py）
  corridor: string;        // 廊：none / surround
  stories: number;
  platform_chi: number;
  length_m: number;
  width_m: number;
  column_m: number;
  evidence: Evidence[];
  notes: string;
  file: string;
}

export interface SceneMeta {
  id: string;
  name: string;
  special: string | null;
  notes: string;
  file: string;
  buildings: Record<string, BuildingMeta>; // 键 = 建筑 key（与网格标签一致）
}

export interface ModelEntry {
  id: string;
  title: string;
  group: ModelGroup;
  scene: string | null; // 景模型对应的景 id；总图为 null
  notes: string;
  sceneCount: number;
  variantOf?: string | null; // 另一版本所属的景 id（如参考图效果版 → haiyantang）；不单列于目录
}

export interface Manifest {
  models: ModelEntry[];
  scenes: Record<string, SceneMeta>;
  waters: Record<string, string>; // OSM 水域 id → 名称
}

/** 点选结果：由网格标签解析而来。 */
export interface Pick {
  scene: string;        // 景 id，或总图中的水域 id
  bkey: string | null;  // 建筑 key（命中某栋建筑时）
  part: string;         // 余下的构件路径，如 "roof"、"pavilion/roof"
}
