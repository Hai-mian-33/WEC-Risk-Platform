"""
config.py — 污染物参数化与全局常数
=====================================

把原先散落在各 calc_*.py 中的硬编码常数（降解系数 K=0.05、不均匀系数 a=0.8、
GB3838 限值梯度、SWAT 输出列索引、单位换算、风险分级阈值）统一收敛到
``Pollutant`` 数据类与本模块的常数中。默认提供 TN；扩展 TP/COD 仅需新增实例。

复刻来源：
  - calc_env_capacity_TN.py   : K_TN=0.05, a=0.8, rch FLOW_OUT(col6)/TOT_Nkg(col47)
  - calc_nps_flux.py          : rch in/out 列 [11,12,15,16,17,18,19,20]; sub 产污列 [14,16,20,21]
  - generate_dynamic_standards.py : C_loose = min(C_strict + 1.0, 2.0)
  - calc_adaptive_standard.py : GB3838-2002 TN 限值梯度
  - calc_risk_index_TN.py     : 风险分级 <0->5, <=1->1, <=2->2, <=3->3, else 4
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List


# ----------------------------------------------------------------------------
# 单位换算
# ----------------------------------------------------------------------------
#   点源浓度通量 1 g/s = 86400 s/d * 1 g / 1000 g/kg = 86.4 kg/d
GS_TO_KGD: float = 86.4
#   月均 -> 体积换算用的平均月长度（天）
DAYS_PER_MONTH: float = 30.4
SECONDS_PER_DAY: float = 86400.0


# ----------------------------------------------------------------------------
# 风险分级（复刻 calc_risk_index_TN.classify_risk）
# ----------------------------------------------------------------------------
def classify_risk(risk_value: float) -> int:
    """风险指数 -> 等级。<0 表示容量被严重超载（负容量）记 5 级。"""
    if risk_value is None:
        return 0
    try:
        v = float(risk_value)
    except (TypeError, ValueError):
        return 0
    if v < 0:
        return 5
    elif v <= 1:
        return 1
    elif v <= 2:
        return 2
    elif v <= 3:
        return 3
    else:
        return 4


RISK_CLASS_LABELS: Dict[int, str] = {
    0: "无数据",
    1: "Ⅰ级 低风险",
    2: "Ⅱ级 较低",
    3: "Ⅲ级 中等",
    4: "Ⅳ级 高风险",
    5: "Ⅴ级 超载",
}

#  与 matplotlib/folium 共用的风险等级配色（1->5 由绿到深红）
RISK_CLASS_COLORS: Dict[int, str] = {
    0: "#cccccc",
    1: "#1a9850",
    2: "#a6d96a",
    3: "#fee08b",
    4: "#f46d43",
    5: "#a50026",
}


# ----------------------------------------------------------------------------
# 污染物配置
# ----------------------------------------------------------------------------
@dataclass
class Pollutant:
    """单一污染物的全部计算参数。默认实例见 ``TN``。"""

    code: str = "TN"
    name_cn: str = "总氮"
    unit: str = "mg/L"

    # —— 容量公式参数 ——
    K_decay: float = 0.05          # 降解/沉积自净系数 (1/d)
    a_coef: float = 0.8            # 不均匀系数 a

    # —— GB3838-2002 水质类别限值梯度 (mg/L) ——
    gb3838_limits: Dict[str, float] = field(default_factory=lambda: {
        "Ⅰ类": 0.2, "Ⅱ类": 0.5, "Ⅲ类": 1.0, "Ⅳ类": 1.5, "Ⅴ类": 2.0,
    })
    # 动态标准放宽：C_loose = min(C_strict + loose_add, loose_cap)
    loose_add: float = 1.0
    loose_cap: float = 2.0

    # —— SWAT output.rch 列索引（read_csv header=None, sep 空白）——
    rch_sub_col: int = 1           # 河段编号
    rch_mon_col: int = 3           # 月份
    rch_flow_col: int = 6          # FLOW_OUT (m^3/s)
    rch_totload_col: int = 47      # TOT_N kg（出口总负荷）
    rch_in_cols: List[int] = field(default_factory=lambda: [11, 15, 17, 19])   # ORGN/NO3/NH4/NO2 IN
    rch_out_cols: List[int] = field(default_factory=lambda: [12, 16, 18, 20])  # ORGN/NO3/NH4/NO2 OUT

    # —— SWAT output.sub 产污列索引（BIGSUB 行 split 后）——
    sub_id_col: int = 1
    sub_mon_col: int = 3
    sub_yield_cols: List[int] = field(default_factory=lambda: [14, 16, 20, 21])  # ORGN/NSURQ/LATNO3/GWNO3 (kg/ha)

    # —— 点源文件命名约定 ——
    #   总表 : PL_Point_{code}.csv ; 逐年 : PL_Point_{code}_{year}.csv
    #   列   : 子流域列 'Subbasin' ; 通量列 'PL_point_{code}_g_s'
    point_subbasin_col: str = "Subbasin"

    @property
    def point_value_col(self) -> str:
        return f"PL_point_{self.code}_g_s"

    def point_file_name(self, year: int | None = None) -> str:
        if year is None:
            return f"PL_Point_{self.code}.csv"
        return f"PL_Point_{self.code}_{year}.csv"

    def classify_standard(self, conc: float) -> str:
        """按 GB3838 限值梯度判定某浓度属于哪一类（复刻 calc_adaptive_standard）。"""
        items = sorted(self.gb3838_limits.items(), key=lambda kv: kv[1])
        for cls, limit in items:
            if conc <= limit + 1e-9:
                return cls
        return items[-1][0]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Pollutant":
        valid = {k: v for k, v in (d or {}).items() if k in cls.__dataclass_fields__}
        return cls(**valid)


# 默认污染物：总氮 TN
TN = Pollutant()

# 总磷 TP —— 映射到 SWAT 的磷输出（rch: TOT Pkg=48, ORGP/MINP 进出=13/14/21/22；
# sub 面源产污: ORGP/SOLP/SEDP=15/17/18）。GB3838 河流 TP 限值。
TP = Pollutant(
    code="TP", name_cn="总磷", unit="mg/L",
    K_decay=0.10, a_coef=0.8,
    gb3838_limits={"Ⅰ类": 0.02, "Ⅱ类": 0.1, "Ⅲ类": 0.2, "Ⅳ类": 0.3, "Ⅴ类": 0.4},
    loose_add=0.1, loose_cap=0.4,
    rch_totload_col=48, rch_in_cols=[13, 21], rch_out_cols=[14, 22],
    sub_yield_cols=[15, 17, 18],
)

# 化学需氧量 COD —— SWAT 标准输出无 COD 状态量，以 CBOD 作为河道内代理（rch CBOD 进出=25/26）；
# output.sub 无 COD 面源产污，故 NPS 需外部数据（sub_yield_cols 置空，面源默认 0）。此为「接口」，
# 使用前请按本地数据核定限值/系数，并提供 COD 点源/监测数据。
COD = Pollutant(
    code="COD", name_cn="化学需氧量", unit="mg/L",
    K_decay=0.20, a_coef=0.8,
    gb3838_limits={"Ⅰ类": 15, "Ⅱ类": 15, "Ⅲ类": 20, "Ⅳ类": 30, "Ⅴ类": 40},
    loose_add=10.0, loose_cap=40.0,
    rch_totload_col=26, rch_in_cols=[25], rch_out_cols=[26],
    sub_yield_cols=[],
)

# 内置污染物接口（TN 已完整验证；TP 映射 SWAT 磷输出；COD 为 CBOD 代理接口，需外部数据）
BUILTIN_POLLUTANTS: Dict[str, Pollutant] = {
    "TN": TN,
    "TP": TP,
    "COD": COD,
}

