"""config.py — 建筑参数 YAML 读取。

优先使用 PyYAML；环境不可用时回退到内置极简解析器
（仅支持本项目 schema：两空格缩进嵌套 dict、标量类型推断、'- ' 列表、
含 ``- key: value`` 起始的 dict 列表项、行内/整行注释；不支持锚点、多行字符串等）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from generator import brackets, carpentry, units

ROOF_XIESHAN = "歇山"
ROOF_XIESHAN_ROUND = "卷棚歇山"  # 卷棚：无正脊、罗锅圆脊（正大光明殿即此式）
GRADES = ("大式", "小式")
SUPPORTED_ROOFS = (
    ROOF_XIESHAN, ROOF_XIESHAN_ROUND,
    "庑殿",                       # 须面阔 > 进深
    "攒尖",                       # 暂只支持四角方亭（面阔 = 进深）
    "硬山", "卷棚硬山",
    "悬山", "卷棚悬山",
)


@dataclass(frozen=True)
class BuildingParams:
    """单体建筑参数（对应 data/buildings/*.yaml 的 building 节）。"""

    id: str
    name: str
    grade: str = "大式"                 # 大式（斗口驱动）/ 小式（明间面宽驱动）
    doukou_cun: float | None = None    # 直接给定斗口（寸），优先于等第
    doukou_grade: int | None = None    # 或按等第查表（1–11）
    bays: int = 7                      # 面阔间数（奇数）
    depth_bays: int = 3                # 进深间数
    bay_brackets: int = 6              # 明间平身科数（决定明间面阔，S-009）
    depth_brackets: int = 4            # 进深每间平身科数（S-010）
    roof: str = ROOF_XIESHAN
    platform_height_chi: float = 3.5   # 台基高（营造尺）
    moon_platform: bool = False        # 月台（正大光明殿有，中型以上殿宇常见）
    stairs_flights: int = 3            # 踏跺路数（三路：中路＋两侧路）
    stairs_steps: int = 9              # 每路级数（九级）
    double_eave: bool = False          # 重檐：檐柱顶加腰檐环带（下檐）
    stories: int = 1                   # 层数：1 单层殿，2 楼（二层，带腰檐）
    ming_bay_chi: float | None = None  # 小式：明间面阔（营造尺）
    side_bay_chi: float | None = None  # 小式：次间面阔（营造尺；缺省明间 × 0.8，S-039）
    depth_bay_chi: float | None = None  # 小式：进深每间（营造尺）
    bracket_set: str | None = None     # 大式斗拱：一斗三升 / 三踩 / 五踩重昂…（缺省不建斗拱层）
    enclosure: str = "front"           # 围护：open 敞 / front 前檐装修 / surround 四面装修 / gate 门殿（carpentry.py）
    corridor: str = "none"             # 廊：none 无 / surround 周围廊（装修退至金柱一线）
    evidence: tuple[dict[str, str], ...] = ()

    @property
    def doukou_cm(self) -> float:
        """斗口（cm）。doukou_cun 优先于 doukou_grade。"""
        if self.doukou_cun is not None:
            return units.cun_to_cm(float(self.doukou_cun))
        if self.doukou_grade is not None:
            return units.doukou_cm(int(self.doukou_grade))
        raise ValueError("须提供 doukou_cun 或 doukou_grade 之一")

    @property
    def platform_height_cm(self) -> float:
        """台基高（cm）。"""
        return units.chi_to_cm(self.platform_height_chi)

    def validate(self) -> None:
        """参数合法性检查（含本步生成器的能力边界）。"""
        if self.grade not in GRADES:
            raise ValueError(f"grade 须为 {GRADES} 之一，收到 {self.grade}")
        if self.grade == "小式":
            for name in ("ming_bay_chi", "depth_bay_chi"):
                v = getattr(self, name)
                if v is None or v <= 0:
                    raise ValueError(f"小式须给出正的 {name}，收到 {v}")
            if self.side_bay_chi is not None and self.side_bay_chi <= 0:
                raise ValueError(f"side_bay_chi 须为正，收到 {self.side_bay_chi}")
            if self.bracket_set:
                raise ValueError("小式建筑无斗拱，不能给 bracket_set")
        elif self.doukou_cun is None and self.doukou_grade is None:
            raise ValueError("大式须提供 doukou_cun 或 doukou_grade 之一")
        if self.bays < 1 or self.bays % 2 == 0:
            raise ValueError(f"面阔间数 bays 须为正奇数，收到 {self.bays}")
        if self.depth_bays < 1:
            raise ValueError(f"进深间数 depth_bays 须 ≥1，收到 {self.depth_bays}")
        if self.bay_brackets < 3:
            raise ValueError(
                f"明间平身科数 bay_brackets 须 ≥3（次间比明间少 1 攒），收到 {self.bay_brackets}"
            )
        if self.depth_brackets < 2:
            raise ValueError(f"进深平身科数 depth_brackets 须 ≥2，收到 {self.depth_brackets}")
        if self.roof not in SUPPORTED_ROOFS:
            raise ValueError(f"屋顶类型仅支持 {SUPPORTED_ROOFS}，收到 {self.roof}")
        if self.platform_height_chi <= 0:
            raise ValueError(f"台基高须为正，收到 {self.platform_height_chi}")
        if self.moon_platform:
            if not 1 <= self.stairs_flights <= 4:
                raise ValueError(f"踏跺路数须在 1–4 之间，收到 {self.stairs_flights}")
            if not 1 <= self.stairs_steps <= 40:
                raise ValueError(f"踏跺级数须在 1–40 之间，收到 {self.stairs_steps}")
        if self.bracket_set:
            brackets.tiao_count(self.bracket_set)
        if self.enclosure not in carpentry.ENCLOSURES:
            raise ValueError(f"enclosure 须为 {carpentry.ENCLOSURES} 之一，收到 {self.enclosure}")
        if self.corridor not in carpentry.CORRIDORS:
            raise ValueError(f"corridor 须为 {carpentry.CORRIDORS} 之一，收到 {self.corridor}")
        if self.corridor == "surround" and (self.bays < 3 or self.depth_bays < 3):
            raise ValueError("周围廊须面阔、进深均 ≥ 3 间")
        if self.stories not in (1, 2):
            raise ValueError(f"层数 stories 仅支持 1 或 2，收到 {self.stories}")


_KNOWN_FIELDS = {
    "id", "name", "grade", "doukou_cun", "doukou_grade", "bays", "depth_bays",
    "bay_brackets", "depth_brackets", "roof", "platform_height_chi",
    "moon_platform", "stairs_flights", "stairs_steps", "double_eave", "stories", "evidence",
    "ming_bay_chi", "side_bay_chi", "depth_bay_chi", "bracket_set", "enclosure", "corridor",
}


@dataclass(frozen=True)
class SceneBuilding:
    """景群中的一栋建筑：参数文件引用 + 方位（间距为工作假设，S-018）。"""

    ref: str
    role: str = ""
    x_cm: float = 0.0
    y_cm: float = 0.0
    rotation_deg: float = 0.0


@dataclass(frozen=True)
class Scene:
    """景群：对应 data/scenes/*.yaml 的 scene 节。"""

    id: str
    name: str
    buildings: tuple[SceneBuilding, ...]
    water: bool = False  # 示意水面（万方安和等水中建筑；非史料形体，S-021）
    island_w_cm: float = 0.0   # 岛台宽（>0 时生成岛面，蓬岛瑶台等湖心岛，S-030）
    island_d_cm: float = 0.0   # 岛台进深
    special: str | None = None  # 专属场景构建器名（如 haiyantang，见 scene._SPECIAL_BUILDERS）


_SCENE_KNOWN_FIELDS = {
    "id", "name", "buildings", "water", "island_w_cm", "island_d_cm", "special",
}
_SCENE_BUILDING_FIELDS = {"ref", "role", "x_cm", "y_cm", "rotation_deg"}


def load_scene(path: str | Path) -> Scene:
    """从 YAML 文件读取景群定义。"""
    text = Path(path).read_text(encoding="utf-8")
    data = _load_yaml(text)
    s = data.get("scene")
    if not isinstance(s, dict):
        raise ValueError("场景文件须包含顶层 scene: 节")
    unknown = set(s) - _SCENE_KNOWN_FIELDS
    if unknown:
        raise ValueError(f"scene 节未知字段: {sorted(unknown)}")
    for required in ("id", "name"):
        if required not in s:
            raise ValueError(f"scene 节缺少必填字段: {required}")
    if "buildings" not in s:
        if not s.get("special"):
            raise ValueError("scene 节缺少必填字段: buildings（无 special 构建器时必填）")
        bs: list = []
    else:
        bs = s["buildings"]
    if not isinstance(bs, list):
        raise ValueError("scene.buildings 须为列表")
    entries: list[SceneBuilding] = []
    for b in bs:
        if not isinstance(b, dict):
            raise ValueError(f"scene.buildings 项须为 dict: {b}")
        unknown_b = set(b) - _SCENE_BUILDING_FIELDS
        if unknown_b:
            raise ValueError(f"scene.buildings 项未知字段: {sorted(unknown_b)}")
        if "ref" not in b:
            raise ValueError("scene.buildings 项缺少 ref")
        rotation = float(b.get("rotation_deg", 0.0))
        if rotation % 90.0 != 0.0:
            raise ValueError(f"rotation_deg 须为 90 的整数倍，收到 {rotation}")
        entries.append(
            SceneBuilding(
                ref=str(b["ref"]),
                role=str(b.get("role", "")),
                x_cm=float(b.get("x_cm", 0.0)),
                y_cm=float(b.get("y_cm", 0.0)),
                rotation_deg=rotation % 360.0,
            )
        )
    return Scene(
        id=str(s["id"]),
        name=str(s["name"]),
        buildings=tuple(entries),
        water=bool(s.get("water", False)),
        island_w_cm=float(s.get("island_w_cm", 0.0)),
        island_d_cm=float(s.get("island_d_cm", 0.0)),
        special=(str(s["special"]) if s.get("special") else None),
    )


@dataclass(frozen=True)
class GardenScene:
    """总园中的一个景：场景文件引用 + 园区偏移与朝向（间距为示意工作假设，S-022）。"""

    ref: str
    x_cm: float = 0.0
    y_cm: float = 0.0
    rotation_deg: float = 0.0


@dataclass(frozen=True)
class GardenLake:
    """示意湖面：矩形（w/d）或多边形（polygon 名，见 generator.terrain）。"""

    name: str
    x_cm: float
    y_cm: float
    w_cm: float = 0.0
    d_cm: float = 0.0
    polygon: str | None = None


@dataclass(frozen=True)
class GardenTerrain:
    """真实水域（OSM 多边形）引用：file 为水多边形 JSON，names 按名称/ID 过滤。"""

    file: str
    names: tuple[str, ...] = ()


@dataclass(frozen=True)
class Garden:
    """总园：对应 data/gardens/*.yaml 的 garden 节。"""

    id: str
    name: str
    scenes: tuple[GardenScene, ...]
    lakes: tuple[GardenLake, ...] = ()
    terrain: GardenTerrain | None = None


_GARDEN_KNOWN_FIELDS = {"id", "name", "scenes", "lakes", "terrain"}
_GARDEN_SCENE_FIELDS = {"ref", "x_cm", "y_cm", "rotation_deg"}
_GARDEN_LAKE_FIELDS = {"name", "x_cm", "y_cm", "w_cm", "d_cm", "polygon"}


def load_garden(path: str | Path) -> Garden:
    """从 YAML 文件读取总园装配定义。"""
    text = Path(path).read_text(encoding="utf-8")
    data = _load_yaml(text)
    g = data.get("garden")
    if not isinstance(g, dict):
        raise ValueError("总园文件须包含顶层 garden: 节")
    unknown = set(g) - _GARDEN_KNOWN_FIELDS
    if unknown:
        raise ValueError(f"garden 节未知字段: {sorted(unknown)}")
    for required in ("id", "name", "scenes"):
        if required not in g:
            raise ValueError(f"garden 节缺少必填字段: {required}")
    ss = g["scenes"]
    if not isinstance(ss, list) or not ss:
        raise ValueError("garden.scenes 须为非空列表")
    scenes: list[GardenScene] = []
    for s in ss:
        if not isinstance(s, dict):
            raise ValueError(f"garden.scenes 项须为 dict: {s}")
        unknown_s = set(s) - _GARDEN_SCENE_FIELDS
        if unknown_s:
            raise ValueError(f"garden.scenes 项未知字段: {sorted(unknown_s)}")
        if "ref" not in s:
            raise ValueError("garden.scenes 项缺少 ref")
        scenes.append(
            GardenScene(
                ref=str(s["ref"]),
                x_cm=float(s.get("x_cm", 0.0)),
                y_cm=float(s.get("y_cm", 0.0)),
                rotation_deg=float(s.get("rotation_deg", 0.0)) % 360.0,
            )
        )
    lakes: list[GardenLake] = []
    for lk in g.get("lakes") or []:
        if not isinstance(lk, dict):
            raise ValueError(f"garden.lakes 项须为 dict: {lk}")
        unknown_l = set(lk) - _GARDEN_LAKE_FIELDS
        if unknown_l:
            raise ValueError(f"garden.lakes 项未知字段: {sorted(unknown_l)}")
        for required in ("name", "x_cm", "y_cm"):
            if required not in lk:
                raise ValueError(f"garden.lakes 项缺少必填字段: {required}")
        poly = lk.get("polygon")
        if poly is None and ("w_cm" not in lk or "d_cm" not in lk):
            raise ValueError("garden.lakes 项须给 polygon 或 w_cm/d_cm")
        lakes.append(
            GardenLake(
                name=str(lk["name"]),
                x_cm=float(lk["x_cm"]),
                y_cm=float(lk["y_cm"]),
                w_cm=float(lk.get("w_cm", 0.0)),
                d_cm=float(lk.get("d_cm", 0.0)),
                polygon=(str(poly) if poly else None),
            )
        )
    return Garden(
        id=str(g["id"]),
        name=str(g["name"]),
        scenes=tuple(scenes),
        lakes=tuple(lakes),
        terrain=_parse_terrain(g.get("terrain")),
    )


def _parse_terrain(raw) -> GardenTerrain | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("garden.terrain 须为 dict")
    unknown = set(raw) - {"file", "names"}
    if unknown:
        raise ValueError(f"garden.terrain 未知字段: {sorted(unknown)}")
    if "file" not in raw:
        raise ValueError("garden.terrain 缺少必填字段: file")
    names = raw.get("names") or []
    if not isinstance(names, list):
        raise ValueError("garden.terrain.names 须为列表")
    return GardenTerrain(file=str(raw["file"]), names=tuple(str(n) for n in names))


def peek_kind(path: str | Path) -> str:
    """探测 YAML 顶层节类型：'garden' / 'scene' / 'building' / 'unknown'。"""
    text = Path(path).read_text(encoding="utf-8")
    data = _load_yaml(text)
    for k in ("garden", "scene", "building"):
        if isinstance(data.get(k), dict):
            return k
    return "unknown"


def load_building(path: str | Path) -> BuildingParams:
    """从 YAML 文件读取建筑参数并做基础校验。"""
    text = Path(path).read_text(encoding="utf-8")
    data = _load_yaml(text)
    if not isinstance(data, dict) or not isinstance(data.get("building"), dict):
        raise ValueError("配置文件须包含顶层 building: 节")
    b = data["building"]
    unknown = set(b) - _KNOWN_FIELDS
    if unknown:
        raise ValueError(f"未知字段: {sorted(unknown)}（已知: {sorted(_KNOWN_FIELDS)}）")
    for required in ("id", "name"):
        if required not in b:
            raise ValueError(f"building 节缺少必填字段: {required}")
    evidence = tuple(
        {"source": str(e.get("source", "")), "confidence": str(e.get("confidence", ""))}
        for e in (b.get("evidence") or [])
        if isinstance(e, dict)
    )
    params = BuildingParams(
        id=str(b["id"]),
        name=str(b["name"]),
        grade=str(b.get("grade", "大式")),
        doukou_cun=(float(b["doukou_cun"]) if b.get("doukou_cun") is not None else None),
        doukou_grade=(int(b["doukou_grade"]) if b.get("doukou_grade") is not None else None),
        bays=int(b.get("bays", 7)),
        depth_bays=int(b.get("depth_bays", 3)),
        bay_brackets=int(b.get("bay_brackets", 6)),
        depth_brackets=int(b.get("depth_brackets", 4)),
        roof=str(b.get("roof", ROOF_XIESHAN)),
        platform_height_chi=float(b.get("platform_height_chi", 3.5)),
        moon_platform=bool(b.get("moon_platform", False)),
        stairs_flights=int(b.get("stairs_flights", 3)),
        stairs_steps=int(b.get("stairs_steps", 9)),
        double_eave=bool(b.get("double_eave", False)),
        stories=int(b.get("stories", 1)),
        ming_bay_chi=_opt_float(b, "ming_bay_chi"),
        side_bay_chi=_opt_float(b, "side_bay_chi"),
        depth_bay_chi=_opt_float(b, "depth_bay_chi"),
        bracket_set=(str(b["bracket_set"]) if b.get("bracket_set") else None),
        enclosure=str(b.get("enclosure", "front")),
        corridor=str(b.get("corridor", "none")),
        evidence=evidence,
    )
    params.validate()
    return params


def _opt_float(d: dict, key: str) -> float | None:
    return float(d[key]) if d.get(key) is not None else None


def _load_yaml(text: str) -> dict:
    """读取 YAML：优先 PyYAML，不可用时使用内置极简解析器。"""
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        return _mini_yaml_load(text)
    result = yaml.safe_load(text)
    return result if isinstance(result, dict) else {}


# ---------------------------------------------------------------------------
# 极简 YAML 子集解析器（PyYAML 缺席时的回退，覆盖本项目 schema）
# ---------------------------------------------------------------------------

_INT_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?$")


def _coerce_scalar(text: str):
    s = text.strip()
    if s in ("true", "True"):
        return True
    if s in ("false", "False"):
        return False
    if _INT_RE.match(s):
        return int(s)
    if _FLOAT_RE.match(s):
        return float(s)
    return s


def _mini_yaml_load(text: str) -> dict:
    """极简 YAML 子集解析器。

    支持：两空格缩进的嵌套 dict、``key: value``（标量类型推断）、
    ``- item`` 列表（字符串项与 ``- key: value`` 起始的 dict 项，可带续行 key）、
    整行与行内注释。不支持锚点、引号转义、多行字符串等高级特性。
    """
    root: dict = {}
    # 栈元素: (该容器的子键基准缩进, 容器)；列表容器用 key 缩进 − 1，便于多个 '- ' 项挂载
    stack: list[tuple[int, object]] = [(-1, root)]
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        content = line.strip()

        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]

        if content.startswith("- "):
            if isinstance(parent, dict) and not parent:
                # 该空 dict 是 valueless key 的占位 → 转换为其父容器中的 list
                stack.pop()
                grand = stack[-1][1]
                for k, v in list(grand.items()):
                    if v is parent:
                        lst: list = []
                        grand[k] = lst
                        parent = lst
                        break
                else:
                    raise ValueError(f"极简解析器：列表项无处挂载: {raw.strip()}")
                stack.append((indent - 1, parent))
            if not isinstance(parent, list):
                raise ValueError(f"极简解析器：'- ' 项不在列表下: {raw.strip()}")
            item = content[2:].strip()
            if ":" in item:
                k, v = item.split(":", 1)
                entry: dict = {k.strip(): _coerce_scalar(v)}
                parent.append(entry)
                stack.append((indent, entry))  # 续行 key（更深缩进）归入本 dict 项
            else:
                parent.append(_coerce_scalar(item))
            continue

        if isinstance(parent, list):
            # '- ' dict 项的续行 key
            if not parent or not isinstance(parent[-1], dict):
                raise ValueError(f"极简解析器：续行 key 不在 dict 项下: {raw.strip()}")
            k, v = content.split(":", 1)
            parent[-1][k.strip()] = _coerce_scalar(v)
            continue

        if ":" not in content:
            raise ValueError(f"极简解析器：无法解析行: {raw.strip()}")
        k, v = content.split(":", 1)
        k = k.strip()
        v = v.strip()
        if v == "":
            child: dict = {}
            parent[k] = child
            stack.append((indent, child))
        else:
            parent[k] = _coerce_scalar(v)
    return root
