"""
project.py — 工程抽象（多流域迁移的基石）
=============================================

一个 Project 描述某流域的全部上下文，可从任意 SWAT2012 工程根目录自动探测，
也可序列化为 project.json 反复加载。除「研究区由用户提供」外，无任何硬编码。

目录约定（与 QSWAT2012 一致）：
    <root>/Watershed/Shapes/subs1.shp, riv1.shp
    <root>/Scenarios/<scenario>/TxtInOut/{file.cio, fig.fig, output.rch, output.sub, SWAT*.exe}
点源/标准表既可放在 <root>，也可放在 scenario 目录，加载时自动搜索。
"""
from __future__ import annotations

import glob
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

from .config import Pollutant, TN
from .swat_io import read_file_cio


# ----------------------------------------------------------------------------
# 标定（动态自适应标准的关键因子与阈值）
# ----------------------------------------------------------------------------
@dataclass
class FactorSpec:
    """一个动态标准调整因子。direction='negative' 表示值越小越需放宽标准。"""
    name: str                       # 因子名，亦即数据列名，如 'Slope_pct'
    direction: str = "negative"     # 'negative' | 'positive'
    threshold: Optional[float] = None
    provenance: str = "default"     # 'monitoring_roc' | 'swat_quantile' | 'manual' | 'default'
    weight: float = 1.0              # normalized in the adaptive weighted mean

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Calibration:
    """因子集合 + 标定元数据。"""
    factors: List[FactorSpec] = field(default_factory=list)
    mode: str = "default"           # 整体标定模式
    auc: Dict[str, float] = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "factors": [f.to_dict() for f in self.factors],
            "mode": self.mode,
            "auc": self.auc,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Calibration":
        d = d or {}
        return cls(
            factors=[FactorSpec(**f) for f in d.get("factors", [])],
            mode=d.get("mode", "default"),
            auc=d.get("auc", {}),
            notes=d.get("notes", ""),
        )

    @property
    def is_provisional(self) -> bool:
        return any(f.provenance in ("swat_quantile", "default") for f in self.factors)


# Miyun 内置工程的默认因子（来自 generate_dynamic_standards.py 的 ROC 阈值）
def default_miyun_calibration() -> Calibration:
    return Calibration(
        factors=[
            FactorSpec("Slope_pct", "negative", 19.152642, "configured_swat_roc", 1.0),
            FactorSpec("Elev_m", "negative", 330.604511, "configured_swat_roc", 1.0),
        ],
        mode="configured_swat_roc",
        notes="密云终稿配置：低值方向 ROC/Youden 点估计；AUC 较弱且阈值区间较宽，只作为流域特定运行估计。",
    )


# ----------------------------------------------------------------------------
# Project
# ----------------------------------------------------------------------------
@dataclass
class Project:
    name: str
    root_dir: str
    scenario: str
    pollutant: Pollutant = field(default_factory=lambda: TN)
    calibration: Calibration = field(default_factory=Calibration)
    # 逐年标定覆盖：{year: Calibration}。某年有则该年的动态标准/容量/风险用之，否则用全局 calibration。
    calibration_by_year: Dict[int, "Calibration"] = field(default_factory=dict)
    years: List[int] = field(default_factory=list)          # SWAT 输出的全部年份
    # 参与「多年平均」基准计算(Wi/浓度/面源)的模拟年份子集；默认=全部输出年份。
    analysis_years: List[int] = field(default_factory=list)
    n_subbasins: int = 0
    # 仅保留编号；个别需要命名的子流域(如水库)放这里 {sub: {"zh":..,"en":..}}
    named_subbasins: Dict[int, dict] = field(default_factory=dict)
    # 容量计算的研究区相关修正（默认通用：无截断、无水库特例）
    #   conc_clip_upper      : deprecated compatibility field; final revision leaves it None
    #   reservoir_overrides  : {sub_id: {"K": .., "V": .., "inflow_conc_cap": ..}}
    conc_clip_upper: Optional[float] = None
    reservoir_overrides: Dict[int, dict] = field(default_factory=dict)
    protection_nodes: List[int] = field(default_factory=list)
    # 数据登记（仅记录，用于校验/溯源，不参与计算）
    data_inputs: Dict[str, str] = field(default_factory=dict)
    # 标准表列名（可按本地命名覆盖）
    std_sub_col: str = "子流域ID(SUB)"
    std_limit_col: Optional[str] = None  # None -> 自动按 '<code>标准限值' 推断
    project_path: Optional[str] = None   # project.json 路径

    # ---- 派生路径 ----------------------------------------------------------
    @property
    def shapes_dir(self) -> str:
        return os.path.join(self.root_dir, "Watershed", "Shapes")

    @property
    def subs_shp(self) -> str:
        return os.path.join(self.shapes_dir, "subs1.shp")

    @property
    def riv_shp(self) -> str:
        return os.path.join(self.shapes_dir, "riv1.shp")

    @property
    def scenario_dir(self) -> str:
        return os.path.join(self.root_dir, "Scenarios", self.scenario)

    @property
    def txtinout(self) -> str:
        return os.path.join(self.scenario_dir, "TxtInOut")

    @property
    def cache_dir(self) -> str:
        return self.scenario_dir

    @property
    def swat_exe(self) -> Optional[str]:
        cands = glob.glob(os.path.join(self.txtinout, "*.exe"))
        cands = [c for c in cands if os.path.basename(c).lower().startswith("swat")]
        return cands[0] if cands else (cands[0] if cands else None)

    @property
    def standards_csv(self) -> Optional[str]:
        for d in (self.scenario_dir, self.root_dir):
            p = os.path.join(d, "subbasin_water_quality_standards.csv")
            if os.path.isfile(p):
                return p
        return None

    def point_source_path(self, year: Optional[int] = None,
                          allow_base: bool = True) -> Optional[str]:
        """搜索点源文件。allow_base=False 时只接受该年专属文件，不回退到总表
        （实际容量计算用严格匹配；面源滞留率用 allow_base=True）。"""
        names = []
        if year is not None:
            names.append(self.pollutant.point_file_name(year))
        if allow_base or year is None:
            names.append(self.pollutant.point_file_name(None))
        for name in names:
            for d in (self.root_dir, self.scenario_dir):
                p = os.path.join(d, name)
                if os.path.isfile(p):
                    return p
        return None

    def data_input_path(self, key: str) -> Optional[str]:
        """Resolve an optional registered data input.

        Relative paths are interpreted from the project root so that the
        public example remains portable after ``git clone``.  Absolute paths
        are retained for private/local projects.
        """
        value = self.data_inputs.get(key)
        if not value:
            return None
        if os.path.isabs(value):
            return os.path.normpath(value)
        return os.path.normpath(os.path.join(self.root_dir, value))

    def has_point_source(self, year: Optional[int]) -> bool:
        """该年是否存在专属点源文件（严格，不回退总表）。"""
        return self.point_source_path(year, allow_base=False) is not None

    @property
    def point_source_years(self) -> List[int]:
        """有专属点源文件、可做完整容量+风险分析的年份。"""
        ys = [y for y in self.years if self.has_point_source(y)]
        return ys

    def calibration_for_year(self, year: Optional[int]) -> "Calibration":
        """返回该年生效的标定：逐年覆盖优先，否则全局。"""
        if year is not None and year in self.calibration_by_year:
            return self.calibration_by_year[year]
        return self.calibration

    def subbasin_name(self, sub: int, lang: str = "zh") -> str:
        """返回需命名子流域的名称（无则空字符串）。"""
        d = self.named_subbasins.get(int(sub)) or self.named_subbasins.get(sub)
        if not d:
            return ""
        return d.get(lang) or d.get("zh") or d.get("en") or ""

    def resolved_std_limit_col(self) -> str:
        return self.std_limit_col or f"{self.pollutant.code}标准限值(mg/L)"

    # ---- 完整性校验 --------------------------------------------------------
    def validate(self) -> List[str]:
        """返回问题列表（空 = 通过）。"""
        problems = []
        checks = {
            "子流域矢量 subs1.shp": self.subs_shp,
            "河网矢量 riv1.shp": self.riv_shp,
            "拓扑文件 fig.fig": os.path.join(self.txtinout, "fig.fig"),
            "河段输出 output.rch": os.path.join(self.txtinout, "output.rch"),
            "子流域输出 output.sub": os.path.join(self.txtinout, "output.sub"),
        }
        for label, path in checks.items():
            if not os.path.isfile(path):
                problems.append(f"缺少 {label}: {path}")
        if self.swat_exe is None:
            problems.append(f"未在 {self.txtinout} 找到 SWAT 可执行文件（仿真功能不可用，仅可分析既有输出）。")
        return problems

    # ---- 序列化 ------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "root_dir": self.root_dir,
            "scenario": self.scenario,
            "pollutant": self.pollutant.to_dict(),
            "calibration": self.calibration.to_dict(),
            "calibration_by_year": {str(y): c.to_dict() for y, c in self.calibration_by_year.items()},
            "years": self.years,
            "analysis_years": self.analysis_years,
            "n_subbasins": self.n_subbasins,
            "named_subbasins": {str(k): v for k, v in self.named_subbasins.items()},
            "conc_clip_upper": self.conc_clip_upper,
            "reservoir_overrides": {str(k): v for k, v in self.reservoir_overrides.items()},
            "protection_nodes": self.protection_nodes,
            "data_inputs": self.data_inputs,
            "std_sub_col": self.std_sub_col,
            "std_limit_col": self.std_limit_col,
        }

    def save(self, path: Optional[str] = None) -> str:
        path = path or self.project_path or os.path.join(self.root_dir, f"{self.name}.wecproj.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        self.project_path = path
        return path

    @classmethod
    def load(cls, path: str) -> "Project":
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        # 相对 root_dir 视为相对于工程文件所在目录，便于随仓库迁移（git clone 后仍可用）
        root = d["root_dir"]
        if not os.path.isabs(root):
            root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(path)), root))
        proj = cls(
            name=d["name"],
            root_dir=root,
            scenario=d["scenario"],
            pollutant=Pollutant.from_dict(d.get("pollutant", {})),
            calibration=Calibration.from_dict(d.get("calibration", {})),
            calibration_by_year={int(y): Calibration.from_dict(c)
                                 for y, c in (d.get("calibration_by_year") or {}).items()},
            years=d.get("years", []),
            analysis_years=d.get("analysis_years", []),
            n_subbasins=d.get("n_subbasins", 0),
            named_subbasins={int(k): v for k, v in (d.get("named_subbasins") or {}).items()},
            conc_clip_upper=d.get("conc_clip_upper"),
            reservoir_overrides={int(k): v for k, v in (d.get("reservoir_overrides") or {}).items()},
            protection_nodes=[int(x) for x in d.get("protection_nodes", [])],
            data_inputs=d.get("data_inputs", {}),
            std_sub_col=d.get("std_sub_col", "子流域ID(SUB)"),
            std_limit_col=d.get("std_limit_col"),
        )
        proj.project_path = path
        return proj

    # ---- 自动探测 ----------------------------------------------------------
    @classmethod
    def detect(cls, root_dir: str, scenario: Optional[str] = None,
               pollutant: Optional[Pollutant] = None,
               name: Optional[str] = None) -> "Project":
        """从 SWAT 工程根目录自动构建 Project（零硬编码）。"""
        root_dir = os.path.abspath(root_dir)
        pollutant = pollutant or TN

        # 选 scenario：优先指定 -> Miyun_Calib_01 -> Default -> 第一个有 TxtInOut 的
        scen_root = os.path.join(root_dir, "Scenarios")
        scenario = scenario or _pick_scenario(scen_root)

        proj = cls(
            name=name or os.path.basename(root_dir.rstrip("/\\")),
            root_dir=root_dir,
            scenario=scenario,
            pollutant=pollutant,
        )

        # 输出年份；analysis_years 默认=全部输出年份
        cio = read_file_cio(proj.txtinout)
        proj.years = cio.get("output_years", [])
        proj.analysis_years = list(proj.years)

        # 子流域数量（数 fig.fig 的 subbasin 命令，或读 subs1.dbf）
        proj.n_subbasins = _count_subbasins(proj)

        # 默认标定：密云沿用原阈值与 v2 修正参数，否则通用（无截断/无特例）
        if "miyun" in proj.name.lower() or scenario == "Miyun_Calib_01":
            proj.calibration = default_miyun_calibration()
            proj.conc_clip_upper = None
            proj.reservoir_overrides = {32: {"K": 0.025, "V": 2.0e9, "inflow_conc_cap": 7.0}}
            proj.protection_nodes = [32]
            proj.named_subbasins = {32: {"zh": "密云水库", "en": "Miyun Reservoir"}}
        else:
            proj.calibration = Calibration(
                factors=[FactorSpec("Slope_pct", "negative", None, "default"),
                         FactorSpec("Elev_m", "negative", None, "default")],
                mode="uncalibrated",
                notes="新工程：关键因子与阈值待在「标定」面板重新确定。",
            )
        return proj


def _pick_scenario(scen_root: str) -> str:
    if not os.path.isdir(scen_root):
        return "Default"
    names = [d for d in os.listdir(scen_root) if os.path.isdir(os.path.join(scen_root, d))]
    for pref in ("Miyun_Calib_01", "Default"):
        if pref in names:
            return pref
    for d in names:
        if os.path.isfile(os.path.join(scen_root, d, "TxtInOut", "file.cio")):
            return d
    return names[0] if names else "Default"


def _count_subbasins(proj: "Project") -> int:
    fig = os.path.join(proj.txtinout, "fig.fig")
    if os.path.isfile(fig):
        n = 0
        with open(fig, "r", errors="ignore") as f:
            for line in f:
                if line.split()[:1] == ["subbasin"]:
                    n += 1
        if n:
            return n
    if os.path.isfile(proj.subs_shp.replace(".shp", ".dbf")):
        try:
            from .swat_io import read_dbf_df
            return len(read_dbf_df(proj.subs_shp.replace(".shp", ".dbf"), ["Subbasin"]))
        except Exception:
            pass
    return 0
