"""bridges.py — 桥亭类建筑（v1：夹镜鸣琴水上桥亭）。

记载（research-fuhai-south.md，书格《圆明园四十景图咏》转录，medium）：
夹镜鸣琴为横跨福海南岸两个小岛之间海峡的**水上桥亭**，白色石桥连接两岛，
桥北福海、桥南港湾小湖，拱洞与倒影如圆镜；东侧山崖流泉"鸣琴"。

v1 几何：西/东桥台（连岛）＋桥身（石桥）＋桥上三间桥亭（简化：桥身实心无拱洞，S-032）。
"""

from __future__ import annotations

from generator import config as config_mod
from generator import mesh as mesh_mod
from generator.assemble import BUILDING_COMPONENTS, build_building_meshes

BRIDGE_LEN_CM = 3600.0    # 桥身长（工作假设，S-032）
DECK_W_CM = 700.0         # 桥身宽（工作假设）
DECK_T_CM = 120.0         # 桥面厚（工作假设）
ABUT_LEN_CM = 900.0       # 桥台长（工作假设）
ABUT_W_CM = 1200.0        # 桥台宽（工作假设）
ABUT_RISE_CM = 30.0       # 桥台高出桥面（拦板示意，S-032）


def build_jiajing_mingqin_scene() -> list[tuple[str, mesh_mod.Mesh]]:
    """夹镜鸣琴桥亭（局部坐标：桥身沿 X，桥亭居中）。"""
    out: list[tuple[str, mesh_mod.Mesh]] = []
    for side, role in ((-1.0, "abutment_west"), (1.0, "abutment_east")):
        cx = side * (BRIDGE_LEN_CM / 2.0 + ABUT_LEN_CM / 2.0)
        out.append((role, mesh_mod.box(
            ABUT_LEN_CM, ABUT_W_CM, 0.0, DECK_T_CM + ABUT_RISE_CM, cx=cx
        )))
    out.append(("deck", mesh_mod.box(BRIDGE_LEN_CM, DECK_W_CM, 0.0, DECK_T_CM)))

    p = config_mod.BuildingParams(
        id="jiajing_ting", name="夹镜鸣琴桥亭", doukou_cun=2.5,
        bays=3, depth_bays=2, bay_brackets=3, depth_brackets=3,
        roof="卷棚歇山", platform_height_chi=0.6,
    )
    p.validate()
    m_platform, m_columns, m_roof, _pl = build_building_meshes(p)
    for comp, m in zip(BUILDING_COMPONENTS, (m_platform, m_columns, m_roof)):
        out.append((f"pavilion/{comp}", m.translated(dz=DECK_T_CM)))
    return out


# 九孔桥（曲院风荷金鳌玉蝀桥）尺寸——孔数九有据，尺寸工作假设（S-033）
NINE_LEN_CM = 6000.0      # 桥身长（圆明三园最大石桥，量级工作假设）
NINE_W_CM = 800.0         # 桥身宽（工作假设）
NINE_DECK_T_CM = 150.0    # 桥面厚（工作假设）
NINE_PIER_CM = 200.0      # 桥墩方量（工作假设）
NINE_PIERS = 8            # 九孔 → 八墩
NINE_ARCH_GAP_CM = 500.0  # 每孔跨（工作假设）
PAILOU_COL_H_CM = 500.0   # 牌楼柱高（工作假设）


def build_quyuan_fenghe_scene() -> list[tuple[str, mesh_mod.Mesh]]:
    """曲院风荷（局部坐标：正殿居北，九孔桥在南北池上沿 X 向，牌楼分立两端）。"""
    out: list[tuple[str, mesh_mod.Mesh]] = []

    # 正殿一排五间（书格转录，medium）
    p = config_mod.BuildingParams(
        id="quyuan_zhengdian", name="曲院风荷正殿", doukou_cun=2.5,
        bays=5, depth_bays=2, bay_brackets=4, depth_brackets=3,
        roof="卷棚歇山", platform_height_chi=2.0,
    )
    p.validate()
    m_platform, m_columns, m_roof, _pl = build_building_meshes(p)
    for comp, m in zip(BUILDING_COMPONENTS, (m_platform, m_columns, m_roof)):
        out.append((f"main_hall/{comp}", m))

    # 九孔大石桥：桥面抬升，下立八墩（九孔示意，未做拱洞 S-033）
    deck_z = 120.0
    out.append(("nine_arch_bridge/deck", mesh_mod.box(NINE_LEN_CM, NINE_W_CM, deck_z, deck_z + NINE_DECK_T_CM)))
    for k in range(NINE_PIERS):
        cx = -NINE_LEN_CM / 2.0 + NINE_ARCH_GAP_CM * (k + 1)
        out.append((f"nine_arch_bridge/pier_{k + 1}",
                    mesh_mod.box(NINE_PIER_CM, NINE_W_CM * 0.8, 0.0, deck_z, cx=cx)))

    # 金鳌（西）/玉蝀（东）牌楼：双柱＋额枋＋顶板
    for role, sx in (("paifang_jinao", -1.0), ("paifang_yudong", 1.0)):
        cx = sx * (NINE_LEN_CM / 2.0 + 150.0)
        gate = mesh_mod.Mesh()
        for sy in (-1.0, 1.0):
            gate = gate.merged(mesh_mod.box(80.0, 80.0, 0.0, PAILOU_COL_H_CM,
                                            cx=cx, cy=sy * 250.0))
        gate = gate.merged(mesh_mod.box(150.0, 660.0, PAILOU_COL_H_CM, PAILOU_COL_H_CM + 80.0, cx=cx))
        gate = gate.merged(mesh_mod.box(240.0, 820.0, PAILOU_COL_H_CM + 80.0,
                                        PAILOU_COL_H_CM + 150.0, cx=cx))
        out.append((role, gate))
    return out
