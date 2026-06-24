"""
pipeline.py — 计算引擎（严格复刻已验证脚本，参数化、可迁移）
=================================================================

两阶段：
  阶段A（重，随 SWAT 运行算一次，缓存 CSV）
    topology -> 关键因子筛选 -> 动态自适应标准 -> 基础容量 Wi -> 面源滞留/输送率
  阶段B（轻，毫秒级，随点源/年份交互）
    实际容量 W_actual = Wi - 点源 -> 拓扑汇流路由 -> 两类风险 -> 高风险/传输热点

复刻来源：extract_topology / generate_dynamic_standards / calc_env_capacity_TN /
          calc_nps_flux / calc_actual_capacity_TN / calc_risk_index_TN / calc_comprehensive_2021
"""
from __future__ import annotations

import ast
import os
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from . import swat_io
from .config import GS_TO_KGD, classify_risk
from .i18n import tr
from .project import Calibration, Project


ProgressCB = Optional[Callable[[str, float], None]]


def _report(cb: ProgressCB, msg: str, frac: float):
    if cb:
        cb(msg, frac)


# ============================================================================
# 动态标准的因子隶属度
# ============================================================================
def _fi_negative(x: float, T: float) -> float:
    """负相关：值越小自净越差/风险越高 -> 越需放宽（返回趋近 1）。"""
    if T is None or T <= 0 or pd.isna(x):
        return 0.0
    if x >= T:
        return 0.0
    if x <= 0.5 * T:
        return 1.0
    return (T - x) / (0.5 * T)


def _fi_positive(x: float, T: float) -> float:
    """正相关：值越大风险越高 -> 越需放宽。对称定义，上饱和点 1.5T。"""
    if T is None or T <= 0 or pd.isna(x):
        return 0.0
    if x <= T:
        return 0.0
    if x >= 1.5 * T:
        return 1.0
    return (x - T) / (0.5 * T)


# ============================================================================
# 标准表 / 点源
# ============================================================================
def load_strict_standards(project: Project, subattr: pd.DataFrame) -> pd.DataFrame:
    """返回 [SUB, C_strict, FuncZone, GB_class]。缺标准表时退回 GB Ⅲ类限值。"""
    pol = project.pollutant
    path = project.standards_csv
    if path and os.path.isfile(path):
        df = pd.read_csv(path, encoding="utf-8-sig")
        sub_col = project.std_sub_col if project.std_sub_col in df.columns else \
            _guess_col(df, ["SUB", "子流域"])
        lim_col = project.resolved_std_limit_col()
        if lim_col not in df.columns:
            lim_col = _guess_col(df, ["限值", pol.code])
        zone_col = _guess_col(df, ["功能区"])
        cls_col = _guess_col(df, ["水质类别", "类别"])
        out = pd.DataFrame()
        out["SUB"] = df[sub_col].astype(float).astype(int)
        out["C_strict"] = pd.to_numeric(df[lim_col], errors="coerce")
        out["FuncZone"] = df[zone_col] if zone_col else ""
        out["GB_class"] = df[cls_col] if cls_col else out["C_strict"].apply(pol.classify_standard)
        return out

    iii = pol.gb3838_limits.get("Ⅲ类", 1.0)
    out = subattr[["SUB"]].copy()
    out["C_strict"] = iii
    out["FuncZone"] = ""
    out["GB_class"] = pol.classify_standard(iii)
    return out


def load_point_source(project: Project, year: Optional[int] = None,
                      strict: bool = False) -> pd.DataFrame:
    """读取点源文件 -> [SUB, point_kgd]（g/s × 86.4）。无文件返回全 0。

    strict=True 时只接受该年专属文件，不回退总表（用于实际容量的逐年相减）。
    """
    pol = project.pollutant
    path = project.point_source_path(year, allow_base=not strict)
    subs = list(range(1, project.n_subbasins + 1)) or []
    if not path:
        return pd.DataFrame({"SUB": subs, "point_kgd": [0.0] * len(subs)})
    df = pd.read_csv(path)
    df = df.rename(columns={pol.point_subbasin_col: "SUB"})
    vcol = pol.point_value_col if pol.point_value_col in df.columns else \
        _guess_col(df, ["g_s", "point"])
    df["point_kgd"] = pd.to_numeric(df[vcol], errors="coerce").fillna(0.0) * GS_TO_KGD
    return df.groupby("SUB", as_index=False)["point_kgd"].sum()


# ============================================================================
# 阶段A
# ============================================================================
@dataclass
class StageAResult:
    topology: pd.DataFrame
    subattr: pd.DataFrame
    screening: pd.DataFrame
    dyn_std: pd.DataFrame          # 默认标定下的动态标准（即时展示用；逐年由阶段B重算）
    base_cap: pd.DataFrame         # 默认标定下的 Wi
    nps: pd.DataFrame
    calibration: Calibration
    rch_agg: pd.DataFrame          # [SUB, FLOW_OUT, conc] 按所选模拟年份聚合（年基准）
    riv_geom: pd.DataFrame         # 河道几何 [SUB, Len2, Wid2, Dep2]
    analysis_years: List[int]      # 实际参与平均的模拟年份


def compute_dynamic_standard(project: Project, subattr: pd.DataFrame,
                             calibration: Optional[Calibration] = None) -> pd.DataFrame:
    """CRS-ACM 动态自适应标准（复刻 generate_dynamic_standards.py，因子通用化）。

    calibration 为 None 时用 project.calibration；传入逐年标定即得该年的动态标准。
    """
    pol = project.pollutant
    calib = calibration or project.calibration
    strict = load_strict_standards(project, subattr)
    df = strict.merge(subattr, on="SUB", how="left")
    df["C_loose"] = np.minimum(df["C_strict"] + pol.loose_add, pol.loose_cap)

    factors = calib.factors
    fi_cols = []
    for f in factors:
        if f.name not in df.columns:
            continue
        T = f.threshold
        if T is None:  # 未标定 -> 用中位数兜底（标 provisional 已在 calibration 处理）
            T = float(df[f.name].median())
        fi = df[f.name].apply(lambda x, T=T, d=f.direction:
                              _fi_negative(x, T) if d == "negative" else _fi_positive(x, T))
        col = f"Fi_{f.name}"
        df[col] = fi
        fi_cols.append(col)

    df["raw_index"] = df[fi_cols].sum(axis=1) if fi_cols else 0.0
    lo, hi = df["raw_index"].min(), df["raw_index"].max()
    df["Adjustment_Index"] = 0.0 if hi == lo else (df["raw_index"] - lo) / (hi - lo)
    df["C_dynamic"] = df["C_strict"] + (df["C_loose"] - df["C_strict"]) * df["Adjustment_Index"]
    df["Recommended_Class"] = df["C_dynamic"].apply(pol.classify_standard)
    return df


def compute_base_capacity(project: Project, topology: pd.DataFrame,
                          dyn_std: pd.DataFrame, rch_agg: pd.DataFrame,
                          riv: pd.DataFrame) -> pd.DataFrame:
    """基础环境容量 Wi（复刻 calc_env_capacity_TN_v2.py：质量加权浓度、不截断负容量、水库特例）。

    rch_agg: 已按所选模拟年份聚合的 [SUB, FLOW_OUT, TN_conc]；riv: 河道几何。
    """
    pol = project.pollutant
    sub_avg = rch_agg.rename(columns={"conc": "TN_conc"}) if "conc" in rch_agg.columns else rch_agg
    df = sub_avg.merge(riv, on="SUB", how="left")
    df["C_it"] = df["SUB"].map(dict(zip(dyn_std["SUB"], dyn_std["C_dynamic"])))
    df["Volume_m3"] = (df["Len2"] * df["Wid2"] * df["Dep2"]).fillna(0.0)

    upstream_map = dict(zip(topology["SUB"], topology["UPSTREAMS"].apply(_as_list)))

    c_ups, q_ups = [], []
    for sub in df["SUB"]:
        ups = upstream_map.get(sub, [])
        tot_q, wmass = 0.0, 0.0
        for u in ups:
            row = df[df["SUB"] == u]
            if not row.empty:
                q = row["FLOW_OUT"].values[0]
                c = row["TN_conc"].values[0]
                tot_q += q
                wmass += q * c
        c_ups.append(wmass / tot_q if tot_q > 0 else 0.0)
        q_ups.append(tot_q)
    df["c_up"] = c_ups
    df["Q_up"] = q_ups

    a = pol.a_coef
    overrides = project.reservoir_overrides or {}
    wis = []
    for _, r in df.iterrows():
        sub = int(r["SUB"])
        if sub in overrides:                       # 水库本体特例（如密云 SUB32）
            ov = overrides[sub]
            K_i = ov.get("K", pol.K_decay)
            V_i = ov.get("V", r["Volume_m3"])
            c_it = ov.get("C_it", r["C_it"])
            df.loc[df["SUB"] == sub, "C_it"] = c_it
            df.loc[df["SUB"] == sub, "Volume_m3"] = V_i
        else:
            K_i, V_i, c_it = pol.K_decay, r["Volume_m3"], r["C_it"]
        Q = r["FLOW_OUT"] if r["Q_up"] == 0 else r["Q_up"]
        term1 = 86.4 * Q * (c_it - r["c_up"])
        term2 = 1e-3 * K_i * V_i * c_it
        wis.append(a * (term1 + term2))            # 不截断负容量（环境赤字）
    df["Wi_kg_d"] = wis
    df["Wi_tons_yr"] = df["Wi_kg_d"] * 365 / 1000.0
    return df[["SUB", "C_it", "Q_up", "c_up", "Volume_m3", "Wi_kg_d", "Wi_tons_yr"]]


def compute_nps_flux(project: Project, subattr: pd.DataFrame,
                     rch: pd.DataFrame) -> pd.DataFrame:
    """面源产污与河道进出通量的「年基准」量（日均 kg/d）。

    返回 [SUB, TN_load_nps_kgd, TN_river_IN_kgd, TN_river_OUT_kgd]。
    滞留/输送率(P_Transport_Rate)与校正面源(TN_nps_corrected)改在阶段B按「该年点源」算，
    使其与所分析年份一致，且不依赖已不存在的总表 PL_Point_<code>.csv（复刻 calc_nps_flux 口径）。
    """
    pol = project.pollutant
    flux = swat_io.rch_retention(rch)

    sub_ids = sorted(subattr["SUB"].astype(int).tolist())
    loads, months = swat_io.read_output_sub(project.txtinout, pol, sub_ids)
    months = months or 1
    area_map = dict(zip(subattr["SUB"], subattr["Area_ha"]))

    rows = []
    for s in sub_ids:
        total_kg = loads.get(s, 0.0) * float(area_map.get(s, 0.0) or 0.0)
        rows.append({"SUB": s, "TN_load_nps_kgd": total_kg / (months * 30.416)})
    df = pd.DataFrame(rows).merge(flux, on="SUB", how="left").fillna(0.0)
    df["TN_river_IN_kgd"] = df["TN_IN"] / (months * 30.416)
    df["TN_river_OUT_kgd"] = df["TN_OUT"] / (months * 30.416)
    return df[["SUB", "TN_load_nps_kgd", "TN_river_IN_kgd", "TN_river_OUT_kgd"]]


def _transport_and_corrected(nps_row_in, nps_row_out, nps_load, point_kgd):
    """按质量守恒算输送率与校正面源（专利 式3/式4），point 用该年点源。"""
    in_total = nps_row_in + nps_load + point_kgd
    if in_total <= 0:
        p_transport = 1.0
    else:
        r = (in_total - nps_row_out) / in_total
        r = min(max(r, 0.0), 1.0)
        p_transport = 1.0 - r
    return p_transport, nps_load * p_transport


def run_stage_a(project: Project, progress_cb: ProgressCB = None,
                cache: bool = True) -> StageAResult:
    """阶段A 全链路：解析 SWAT 输出（按所选模拟年份）并产出年基准量与默认标定结果。"""
    from .calibration import screen_factors

    _report(progress_cb, tr("解析河网拓扑 (fig.fig) ...", "Parsing river topology (fig.fig) ..."), 0.05)
    topology = swat_io.parse_fig_topology(project.txtinout)

    _report(progress_cb, tr("读取子流域属性 (subs1.dbf) ...", "Reading subbasin attributes (subs1.dbf) ..."), 0.12)
    subattr = swat_io.read_subbasin_attrs(project.shapes_dir)

    # 解析 output.rch，并按所选模拟年份过滤（analysis_years 为全部时不过滤，更快）
    cio = swat_io.read_file_cio(project.txtinout)
    out_years = cio.get("output_years", [])
    sel_years = [y for y in (project.analysis_years or out_years) if y in out_years] or out_years
    year_filter = None if set(sel_years) == set(out_years) else sel_years
    yr_msg = tr("全部", "all") if year_filter is None else ",".join(map(str, sel_years))
    _report(progress_cb, tr(f"解析 output.rch（模拟年份: {yr_msg}）...",
                            f"Parsing output.rch (sim years: {yr_msg}) ..."), 0.20)
    rch = swat_io.read_output_rch(project.txtinout, project.pollutant,
                                  years=year_filter, cio=cio)
    rch_agg = swat_io.rch_annual_means(rch, conc_clip_upper=project.conc_clip_upper)
    riv_geom = swat_io.read_river_geometry(project.shapes_dir)

    _report(progress_cb, tr("关键因子筛选 (MI + Spearman) ...", "Key-factor screening (MI + Spearman) ..."), 0.35)
    try:
        screening = screen_factors(project.scenario_dir, project.txtinout,
                                   project.pollutant, subattr)
    except Exception as e:  # 筛选失败不应阻断主链路
        screening = pd.DataFrame()
        _report(progress_cb, tr(f"[警告] 因子筛选跳过：{e}", f"[warn] screening skipped: {e}"), 0.35)

    _report(progress_cb, tr("计算动态自适应标准 (CRS-ACM) ...", "Computing dynamic adaptive standard (CRS-ACM) ..."), 0.55)
    dyn_std = compute_dynamic_standard(project, subattr, project.calibration)

    _report(progress_cb, tr("计算基础环境容量 Wi ...", "Computing base capacity Wi ..."), 0.72)
    base_cap = compute_base_capacity(project, topology, dyn_std, rch_agg, riv_geom)

    _report(progress_cb, tr("计算面源滞留与输送率 ...", "Computing NPS retention/transport ..."), 0.88)
    nps = compute_nps_flux(project, subattr, rch)

    result = StageAResult(topology, subattr, screening, dyn_std, base_cap, nps,
                          project.calibration, rch_agg, riv_geom, sel_years)
    if cache:
        _cache_stage_a(project, result)
    _report(progress_cb, tr(f"阶段A 完成（模拟年份: {yr_msg}）。",
                            f"Stage A done (sim years: {yr_msg})."), 1.0)
    return result


# ============================================================================
# 阶段B
# ============================================================================
def run_stage_b(project: Project, sa: StageAResult,
                point_df: Optional[pd.DataFrame] = None,
                year: Optional[int] = None, cache: bool = True) -> pd.DataFrame:
    """阶段B：按年份生效标定重算动态标准与 Wi，再算实际容量 + 两类风险 + 热点。

    - 逐年标定：用 project.calibration_for_year(year) → 动态标准随之变化 → Wi/容量/风险随之变化；
      若该年无逐年标定则用全局标定，故"用某年标定某年"不影响其他年份。
    - 点源可用性：仅当该年存在专属点源文件(或用户已手动输入 point_df)时才计算实际容量与风险；
      否则实际容量/风险输出为空(NaN)，仅保留动态标准与基础容量。
    """
    pol = project.pollutant

    # 按该年生效标定重算动态标准与基础容量（关键：新阈值真正用于标准/容量/风险）
    calib = project.calibration_for_year(year)
    dyn_std = compute_dynamic_standard(project, sa.subattr, calib)
    base_cap = compute_base_capacity(project, sa.topology, dyn_std, sa.rch_agg, sa.riv_geom)

    # 点源可用性：手动输入优先；否则严格匹配该年专属文件（不回退总表）
    if point_df is not None:
        available = True
    else:
        available = project.has_point_source(year)
        point_df = load_point_source(project, year, strict=True) if available else None

    base = base_cap.merge(sa.nps[["SUB", "TN_load_nps_kgd", "TN_river_IN_kgd",
                                  "TN_river_OUT_kgd"]], on="SUB", how="left").fillna(0.0)

    if not available:
        # 无点源 -> 不输出实际容量/风险，仅保留动态标准与基础容量
        df = base.copy()
        for c in ["point_load_kgd", "W_actual_kg_d", "P_Transport_Rate",
                  "TN_nps_corrected_kgd", "LP", "TR",
                  "Influx_kgd", "Outflux_kgd", "Import_Fraction"]:
            df[c] = np.nan
        df["RiskClass_LP"] = 0
        df["RiskClass_TR"] = 0
        df["Node_Type"] = "N/A"
        df["IsTransmissionHotspot"] = False
        df["IsPriorityArea"] = False
        return _attach_geo(project, df, dyn_std, sa, year, cache, available=False)

    # 实际容量 = Wi - 该年点源
    df = base.merge(point_df.rename(columns={"point_kgd": "point_load_kgd"}),
                    on="SUB", how="left").fillna({"point_load_kgd": 0.0})
    df["W_actual_kg_d"] = df["Wi_kg_d"] - df["point_load_kgd"]

    # 输送率与校正面源：按「该年点源」算（年一致；不依赖总表），复刻 calc_nps_flux 公式
    pt, corr = [], []
    for _, r in df.iterrows():
        p, c = _transport_and_corrected(r["TN_river_IN_kgd"], r["TN_river_OUT_kgd"],
                                        r["TN_load_nps_kgd"], r["point_load_kgd"])
        pt.append(p)
        corr.append(c)
    df["P_Transport_Rate"] = pt
    df["TN_nps_corrected_kgd"] = corr

    df["W_actual_safe"] = np.where(df["W_actual_kg_d"] == 0, 1e-10, df["W_actual_kg_d"])
    # 第一风险值 LP = 实际(校正后)非点源污染物通量 / 实际水环境容量  （专利 式7，本地自身风险）
    df["LP"] = df["TN_nps_corrected_kgd"] / df["W_actual_safe"]

    # 拓扑汇流路由（复刻 calc_risk_index 的 Kahn 排序）
    topo = sa.topology
    ups = dict(zip(topo["SUB"], topo["UPSTREAMS"].apply(_as_list)))
    down = dict(zip(topo["SUB"], topo["TO_SUB"]))
    sub_ids = df["SUB"].tolist()
    influx = {s: 0.0 for s in sub_ids}
    outflux = {s: 0.0 for s in sub_ids}
    indeg = {s: len([u for u in ups.get(s, []) if u in sub_ids]) for s in sub_ids}
    queue = [s for s in sub_ids if indeg[s] == 0]
    order = []
    while queue:
        node = queue.pop(0)
        order.append(node)
        to = down.get(node)
        if pd.notna(to) and to in indeg:
            indeg[to] -= 1
            if indeg[to] == 0:
                queue.append(to)

    rowmap = df.set_index("SUB")
    for s in order:
        r = rowmap.loc[s]
        tr = r["P_Transport_Rate"]
        val_out = (influx[s] + r["point_load_kgd"] + r["TN_load_nps_kgd"]) * tr
        outflux[s] = val_out
        to = down.get(s)
        if pd.notna(to) and to in influx:
            influx[to] += val_out

    df["Influx_kgd"] = df["SUB"].map(influx)
    df["Outflux_kgd"] = df["SUB"].map(outflux)
    # 第二风险值 TR = 上游流入污染物通量 Influx / 实际水环境容量  （专利 式8，上游传输风险）
    # 与第一风险(本地)互不重叠：分子分别为「本地面源」与「上游来量」，不再用累积 Outflux。
    df["TR"] = df["Influx_kgd"] / df["W_actual_safe"]
    df["RiskClass_LP"] = df["LP"].apply(classify_risk)
    df["RiskClass_TR"] = df["TR"].apply(classify_risk)

    # 热点识别：上游流入主导且第二风险高 -> 传输热点
    df["Import_Fraction"] = np.where(df["Outflux_kgd"] > 0,
                                     df["Influx_kgd"] / df["Outflux_kgd"], 0.0)
    df["Node_Type"] = np.where(df["Import_Fraction"] >= 0.5, "Transport hotspot",
                       np.where(df["TN_load_nps_kgd"] + df["point_load_kgd"] > 0,
                                "Source-dominated", "Normal"))
    df["IsTransmissionHotspot"] = (df["RiskClass_TR"] >= 4) & (df["Import_Fraction"] >= 0.5)
    df["IsPriorityArea"] = (df["RiskClass_LP"] >= 4) | (df["RiskClass_TR"] >= 4)

    return _attach_geo(project, df, dyn_std, sa, year, cache, available=True)


def _attach_geo(project: Project, df: pd.DataFrame, dyn_std: pd.DataFrame,
                sa: StageAResult, year, cache: bool, available: bool) -> pd.DataFrame:
    """并入该年动态标准的展示列与几何坐标，重命名 C_it->C_dynamic，并缓存。"""
    pol = project.pollutant
    df = df.merge(dyn_std[["SUB", "C_strict", "C_loose", "Adjustment_Index",
                           "Recommended_Class", "GB_class", "FuncZone"]],
                  on="SUB", how="left")
    df = df.merge(sa.subattr[["SUB", "Lat", "Lon", "Area_ha", "Slope_pct", "Elev_m"]],
                  on="SUB", how="left")
    df = df.rename(columns={"C_it": "C_dynamic"})
    df.attrs["point_available"] = available
    if cache:
        out = os.path.join(project.cache_dir, f"risk_index_{pol.code}"
                           f"{('_' + str(year)) if year else ''}_platform.csv")
        df.to_csv(out, index=False, encoding="utf-8-sig")
    return df


# ============================================================================
# 缓存 / 工具
# ============================================================================
def _cache_stage_a(project: Project, sa: StageAResult):
    d = project.cache_dir
    code = project.pollutant.code
    sa.topology.to_csv(os.path.join(d, "subbasin_topology_platform.csv"), index=False)
    sa.dyn_std.to_csv(os.path.join(d, f"adaptive_standard_{code}_platform.csv"),
                      index=False, encoding="utf-8-sig")
    sa.base_cap.to_csv(os.path.join(d, f"subbasin_environment_capacity_{code}_platform.csv"),
                       index=False)
    sa.nps.to_csv(os.path.join(d, f"nps_corrected_flux_{code}_platform.csv"), index=False)
    if sa.screening is not None and not sa.screening.empty:
        sa.screening.to_csv(os.path.join(d, "feature_screening_platform.csv"),
                            index=False, encoding="utf-8-sig")


def _as_list(v) -> List[int]:
    if isinstance(v, list):
        return v
    if pd.isna(v):
        return []
    try:
        return list(ast.literal_eval(str(v)))
    except (ValueError, SyntaxError):
        return []


def _guess_col(df: pd.DataFrame, keywords: List[str]) -> Optional[str]:
    for c in df.columns:
        for k in keywords:
            if k in str(c):
                return c
    return None
