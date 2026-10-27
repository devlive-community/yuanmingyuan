import type { BuildingMeta, ModelGroup, Pick, SceneMeta } from './types';

// 网格标签（英文 id）→ 页面显示用中文。生成器只输出英文标签，中文只在这里定义。
const PARTS: Record<string, string> = {
  platform: '台基', columns: '柱网', brackets: '斗拱', roof: '屋顶', water: '水面', island: '岛台',
  limestone: '石作（米白）', arcade: '券廊', recess: '券洞', rock_fountain: '池心假山喷泉', shell_cartouche: '贝壳卷涡雕饰',
  ornament: '檐饰与花环', statues: '立像', trees: '乔木', tree: '乔木', cypress: '柏树', leaves: '树叶', viewpoint: '人视机位', centre: '主喷', ring: '环喷',
  beams: '檐枋', red_wall: '墙身（红灰）', wall_base: '下碱与槛墙', joinery: '槛框与槅扇槛窗', paper: '窗户纸',
  cascade: '叠落喷水槽', abutment_west: '西桥台', abutment_east: '东桥台', deck: '桥身',
  pavilion: '桥亭', main_hall: '正殿', nine_arch_bridge: '九孔桥', pier: '桥墩',
  paifang_jinao: '金鳌牌楼', paifang_yudong: '玉蝀牌楼', lake: '湖',
  // 西洋楼 · 海晏堂（末段为材质类）
  walls: '墙身', windows: '门窗', marble: '汉白玉石作', glazed_roof: '琉璃瓦顶', bronze: '铜首',
  tin: '锡板池壁', paving: '铺地', crest: '门罩山花', door: '黄铜正门', medallions_green: '琉璃番花（绿）',
  medallions_yellow: '琉璃番花（黄）', roof_fish: '翻尾石鱼', stone_leopards: '石豹',
  window_trim: '窗套', facade: '立面墙皮', glazed_ridge: '黄琉璃脊', trim: '线脚与勒脚', pilasters: '壁柱',
  front_building: '正楼', wing_south: '南翼平台小屋', wing_north: '北翼平台小屋', rear_hall: '楼后三间殿',
  west_stairs: '叠落石跑梯', zodiac_pool: '生肖喷水池', shell: '石蚌', center_fountain: '喷水塔',
  stone_urn_south: '南八角石鼎', stone_urn_north: '北八角石鼎', court: '楼前广场',
  reservoir_hall: '工字蓄水楼', tin_sea: '锡海', waterwheel_house_west: '西水车房',
  waterwheel_house_east: '东水车房', east_stairs: '东面四折石梯',
  zodiac_rat: '子鼠', zodiac_ox: '丑牛', zodiac_tiger: '寅虎', zodiac_rabbit: '卯兔',
  zodiac_dragon: '辰龙', zodiac_snake: '巳蛇', zodiac_horse: '午马', zodiac_goat: '未羊',
  zodiac_monkey: '申猴', zodiac_rooster: '酉鸡', zodiac_dog: '戌狗', zodiac_pig: '亥猪',
  fountain_south_west: '楼南西八角池', fountain_south_center: '楼南圆形喷泉', fountain_south_east: '楼南东八角池',
  yuanyingguan_terrace: '远瀛观高台', yuanyingguan: '远瀛观', gold_roof: '鱼鳞金瓦顶',
  dashuifa_niche: '大水法石龛', dashuifa_cascade: '七级水台', dashuifa_pool: '海棠喷水池',
  deer: '铜鹿', hounds_west: '西五犬', hounds_east: '东五犬',
  fountain_tower_west: '西十三层喷水塔', fountain_tower_east: '东十三层喷水塔',
  topiary_south: '楼南修剪树', topiary_north: '楼北修剪树', pines: '线法松', foliage: '树冠', bark: '树干',
  guanshuifa: '观水法', guanshuifa_throne: '宝座与铜鹤', plaza: '广场',
  fountain_north_west: '楼北西八角池', fountain_north_center: '楼北圆形喷泉', fountain_north_east: '楼北东八角池',
};

export const GROUP_NAMES: Record<ModelGroup, string> = {
  overview: '总览',
  scenes: '景区',
  samples: '生成器样例（非复原）',
};

export const LEGEND: Array<[string, string]> = [
  ['platform', '#a59e93'],
  ['columns', '#7a1a14'],
  ['brackets', '#2a4f4f'],
  ['red_wall', '#8c3426'],
  ['joinery', '#6b170e'],
  ['roof', '#5c5e66'],
  ['water', '#2a475c'],
];

/** 单段构件名：已知直接查表；带序号的（pier_3、zodiac_plinth_12）拆出序号。 */
export function partZh(seg: string): string {
  if (PARTS[seg]) return PARTS[seg];
  const m = /^(.*)_(\d+)$/.exec(seg);
  if (m && PARTS[m[1]]) return PARTS[m[1]] + m[2];
  return seg;
}

export const partLabel = (part: string): string => part.split('/').map(partZh).join('·');

/**
 * 解析网格标签。景模型：「建筑key/构件」；总图：「景id/建筑key/构件」；
 * 专属构建器部件可多段（pavilion/roof）；总图水域为「water_xxx/water」。
 */
export function parseLabel(
  label: string,
  currentScene: string | null,
  scenes: Record<string, SceneMeta>,
): Pick {
  const segs = label.split('/');
  const scene = currentScene ?? segs.shift() ?? '';
  const s = scenes[scene];
  const bkey = s && segs.length >= 2 && s.buildings[segs[0]] ? segs[0] : null;
  return { scene, bkey, part: (bkey ? segs.slice(1) : segs).join('/') };
}

export function hasSpeculative(b: BuildingMeta): boolean {
  return b.evidence.some((e) => e.confidence === 'low' || e.confidence === 'placeholder');
}
