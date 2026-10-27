#!/usr/bin/env python3
"""osm_to_terrain.py — 把 OSM 区域地图 XML 中的自然水域转换为地形数据（v2：含水体关系）。

用法：
    python3 tools/osm_to_terrain.py build/osm_map.xml data/terrain/water_polygons.json [锚点JSON]

处理：
1. 解析 OSM XML：闭合 way 且 natural=water，以及 natural=water 的 relation
   （取其 outer 成员环；一关系多外环时逐环输出为 name·i，v1 简化）。
2. 经纬度 → 局部平面坐标（米，等距圆柱近似，原点取全部水域西南角）×100 → cm；
   简化：沿环剔除间距 < 12 m 的点。
3. 可选锚点 JSON（[{"name":..., "lat":..., "lon":...}]）→ 每锚点找最近水域并标注。

输出 JSON：{origin, polygons:[{id, name, osm_id, kind, coords_cm, area_m2, centroid_cm}]}。
数据来源：© OpenStreetMap 贡献者（ODbL），仅作示意地形底图（S-028）。
"""

import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

M_PER_DEG = 111320.0
MIN_SPACING_M = 12.0


def way_points(w, nodes):
    return [nodes[nd.get("ref")] for nd in w.findall("nd") if nd.get("ref") in nodes]


def parse_water(xml_path: str):
    root = ET.parse(xml_path).getroot()
    nodes = {n.get("id"): (float(n.get("lat")), float(n.get("lon"))) for n in root.findall("node")}
    ways = {w.get("id"): w for w in root.findall("way")}
    rel_water = {
        r.get("id"): {t.get("k"): t.get("v") for t in r.findall("tag")}
        for r in root.findall("relation")
        if any(t.get("k") == "natural" and t.get("v") == "water" for t in r.findall("tag"))
    }
    used_by_rel: set[str] = set()
    polys = []  # {name, osm_id, kind, latlon}
    for rid, tags in rel_water.items():
        outers = [
            m.get("ref")
            for m in next(r for r in root.findall("relation") if r.get("id") == rid).findall("member")
            if m.get("type") == "way" and m.get("role") in ("outer", "")
        ]
        for i, ref in enumerate(outers):
            w = ways.get(ref)
            if w is None:
                continue
            used_by_rel.add(ref)
            pts = way_points(w, nodes)
            if len(pts) >= 4 and pts[0] == pts[-1]:
                name = tags.get("name", "") or ""
                polys.append({
                    "name": f"{name}·{i}" if len(outers) > 1 and name else (name or ""),
                    "osm_id": f"{rid}/{ref}", "kind": "relation", "latlon": pts,
                })
    for wid, w in ways.items():
        if wid in used_by_rel:
            continue
        tags = {t.get("k"): t.get("v") for t in w.findall("tag")}
        if tags.get("natural") != "water":
            continue
        pts = way_points(w, nodes)
        if len(pts) >= 4 and pts[0] == pts[-1]:
            polys.append({"name": tags.get("name", ""), "osm_id": wid, "kind": "way", "latlon": pts})
    return polys


def to_local_cm(latlon, lat0, lon0):
    coslat = math.cos(math.radians(lat0))
    return [((lon - lon0) * M_PER_DEG * coslat * 100.0, (lat - lat0) * M_PER_DEG * 100.0)
            for (lat, lon) in latlon]


def simplify(points_cm, min_spacing_m=MIN_SPACING_M):
    keep = [points_cm[0]]
    min_cm = min_spacing_m * 100.0
    for p in points_cm[1:]:
        q = keep[-1]
        if math.hypot(p[0] - q[0], p[1] - q[1]) >= min_cm:
            keep.append(p)
    if len(keep) >= 3:
        keep.append(keep[0])
    return keep


def shoelace_area_cm2(pts):
    s = 0.0
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        s += x0 * y1 - x1 * y0
    return abs(s) / 2.0


def main():
    if len(sys.argv) not in (3, 4):
        raise SystemExit(__doc__)
    xml_path, out_path = sys.argv[1], sys.argv[2]
    anchors = []
    if len(sys.argv) == 4:
        anchors = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))

    raw = parse_water(xml_path)
    if not raw:
        raise SystemExit("未找到自然水域")
    lat0 = min(p[0] for w in raw for p in w["latlon"])
    lon0 = min(p[1] for w in raw for p in w["latlon"])
    coslat = math.cos(math.radians(lat0))

    polygons = []
    for w in raw:
        coords = simplify(to_local_cm(w["latlon"], lat0, lon0))
        if len(coords) < 4:
            continue
        area_m2 = shoelace_area_cm2(coords) / 10000.0
        cx = sum(p[0] for p in coords) / len(coords)
        cy = sum(p[1] for p in coords) / len(coords)
        polygons.append({
            "id": f"water_{w['osm_id'].replace('/', '_')}",
            "name": w["name"],
            "osm_id": w["osm_id"],
            "kind": w["kind"],
            "coords_cm": [[round(x, 1), round(y, 1)] for (x, y) in coords],
            "area_m2": round(area_m2, 0),
            "centroid_cm": [round(cx, 1), round(cy, 1)],
        })
    polygons.sort(key=lambda p: -p["area_m2"])

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(
        json.dumps({"origin": {"lat": lat0, "lon": lon0}, "polygons": polygons},
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"水域 {len(polygons)} 块 → {out_path}（原点 lat {lat0:.5f} / lon {lon0:.5f}）")
    print("面积排序（前 12）：")
    for p in polygons[:12]:
        print(f"  {p['area_m2']:>9.0f} m²  {p['name'] or '(未命名)':<10} 质心 "
              f"({p['centroid_cm'][0]:>9.1f}, {p['centroid_cm'][1]:>9.1f})  {p['kind']}  {p['id']}")
    if anchors:
        for a in anchors:
            ax = (a["lon"] - lon0) * M_PER_DEG * coslat * 100.0
            ay = (a["lat"] - lat0) * M_PER_DEG * 100.0
            best = min(polygons, key=lambda p: math.hypot(p["centroid_cm"][0] - ax, p["centroid_cm"][1] - ay))
            dist = math.hypot(best["centroid_cm"][0] - ax, best["centroid_cm"][1] - ay) / 100.0
            print(f"锚点 {a['name']} ({a['lat']:.4f},{a['lon']:.4f}) → 最近水域 {best['name'] or best['id']} "
                  f"（质心距 {dist:.0f} m，面积 {best['area_m2']:.0f} m²）")


if __name__ == "__main__":
    main()
