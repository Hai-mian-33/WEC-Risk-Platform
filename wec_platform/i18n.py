"""
i18n.py — 中英双语支持
========================

极简语言切换：全局当前语言 + tr(zh, en) 取词。UI 文本一律写成 tr("中文","English")，
切换语言时重建界面即可。风险/图层/节点类型等数据型标签集中在此双语化。
"""
from __future__ import annotations

_LANG = "zh"   # "zh" | "en"


def set_lang(lang: str):
    global _LANG
    _LANG = "en" if str(lang).lower().startswith("en") else "zh"


def get_lang() -> str:
    return _LANG


def is_en() -> bool:
    return _LANG == "en"


def tr(zh: str, en: str) -> str:
    """根据当前语言返回中文或英文。"""
    return en if _LANG == "en" else zh


# ---- 数据型双语标签 --------------------------------------------------------
_RISK_ZH = {0: "无数据", 1: "Ⅰ级 低风险", 2: "Ⅱ级 较低", 3: "Ⅲ级 中等",
            4: "Ⅳ级 高风险", 5: "Ⅴ级 超载(赤字)"}
_RISK_EN = {0: "No data", 1: "I Low", 2: "II Lower", 3: "III Medium",
            4: "IV High", 5: "V Overload (deficit)"}


def risk_label(c) -> str:
    try:
        c = int(c)
    except (TypeError, ValueError):
        return "—"
    return (_RISK_EN if _LANG == "en" else _RISK_ZH).get(c, "—")


_NODE_ZH = {"Transport hotspot": "传输热点", "Source-dominated": "本地源主导", "Normal": "一般"}
_NODE_EN = {"Transport hotspot": "Transport hotspot", "Source-dominated": "Source-dominated",
            "Normal": "Normal"}


def node_label(v) -> str:
    v = str(v)
    return (_NODE_EN if _LANG == "en" else _NODE_ZH).get(v, v)


_GB_EN = {"Ⅰ类": "Class I", "Ⅱ类": "Class II", "Ⅲ类": "Class III",
          "Ⅳ类": "Class IV", "Ⅴ类": "Class V", "劣Ⅴ类": "Worse than V"}


def gb_label(v) -> str:
    """GB3838 水质类别中英显示（Ⅲ类 <-> Class III）。"""
    v = str(v).strip()
    if not v or v in ("nan", "None", "—"):
        return "—"
    return _GB_EN.get(v, v) if _LANG == "en" else v
