"""generator — 清式建筑参数化生成器（圆明园数字复原）。

模块划分：
- units    模数与单位换算（常量集中处）
- mesh     纯数据网格与基础形体
- plan     柱网平面几何
- platform 台基
- columns  柱网（檐柱 / 金柱 / 柱础）
- roof     屋顶（歇山 / 庑殿 / 攒尖 / 硬山 / 悬山，简化）
- config   建筑参数 YAML 读取
- assemble Blender 组装入口（依赖 bpy，仅 Blender 内运行）

除 ``assemble`` 外的模块均为纯函数（参数 → Mesh），不依赖 bpy，
可在无 Blender 环境下运行与单测（项目编码规范）。
"""

__all__ = ["units", "mesh", "plan", "platform", "columns", "roof", "config"]
