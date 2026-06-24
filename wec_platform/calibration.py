"""
calibration.py — 关键因子筛选 + 混合阈值标定
================================================

两件事，刻意分开（呼应方法学定调）：

  1) screen_factors()  关键因子「筛选」——纯用 SWAT 模拟数据做 MI + Spearman
     相关分析（复刻 feature_selection.py），附 p 值与 bootstrap 稳定性。
     这一步是「已标定模型上的驱动力分析」，逻辑成立。

  2) calibrate_thresholds() 阈值「标定」——三模式：
        - 'monitoring_roc' 监测数据驱动：Youden/ROC（最严谨，保留独立验证）
        - 'swat_quantile'  无监测退回：因子分位数（标 provisional）
        - 'manual'         手动覆写
     validate_standard() 复刻 CRS-ACM 说明书的 AUC/准确率/特异度，
     验证因子用独立生物响应（藻细胞），与标准判定法则割裂以「切断自循环」。
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .config import Pollutant
from .project import Calibration, FactorSpec


CANDIDATE_FEATURES = ["PRECIPmm", "SYLDt_ha", "Slope_pct", "Elev_m",
                      "AGRL_pct", "FRST_pct", "PAST_pct", "URBN_pct", "WATR_pct"]


# ============================================================================
# 1) 关键因子筛选（复刻 feature_selection.py，含 fallback）
# ============================================================================
def _build_feature_table(scenario_dir: str, txtinout: str,
                         pollutant: Pollutant, subattr: pd.DataFrame
                         ) -> Tuple[pd.DataFrame, List[str], str]:
    """构造 (特征+目标) 表，返回 (df, feature_cols, target_col)。

    优先使用既有 extract_sub.csv / extract_rch.csv（复刻原管线全特征集）；
    缺失时退回：以 subs1.dbf 的 Slope/Elev/Area + output.rch 的 TN 负荷构造精简特征集。
    """
    f_sub = _find_first([os.path.join(scenario_dir, "extract_sub.csv"),
                         os.path.join(txtinout, "extract_sub.csv")])
    f_rch = _find_first([os.path.join(scenario_dir, "extract_rch.csv"),
                         os.path.join(txtinout, "extract_rch.csv")])

    if f_sub and f_rch:
        sub = pd.read_csv(f_sub)
        rch = pd.read_csv(f_rch)
        # extract_*.csv 是「子流域 × 月」长表（每个 SUB 多行）。子流域分区因子是
        # 截面量（n=子流域数），先按 SUB/RCH 聚合为每个单元一行，避免 144×144 自乘爆炸。
        if "SUB" in sub.columns and sub["SUB"].duplicated().any():
            sub = sub.groupby("SUB", as_index=False).mean(numeric_only=True)
        if "RCH" in rch.columns and rch["RCH"].duplicated().any():
            rch = rch.groupby("RCH", as_index=False).mean(numeric_only=True)
        df = pd.merge(sub, rch, left_on="SUB", right_on="RCH", how="inner")
        if {"ORGN_OUTkg", "NO3_OUTkg", "NH4_OUTkg", "Area_ha"}.issubset(df.columns):
            df["target_load"] = (df["ORGN_OUTkg"] + df["NO3_OUTkg"] + df["NH4_OUTkg"]) / df["Area_ha"]
        else:
            df["target_load"] = np.nan
        feats = [c for c in CANDIDATE_FEATURES if c in df.columns]
        return df, feats, "target_load"

    # —— fallback：精简特征集 ——
    from .swat_io import read_output_rch, rch_annual_means
    rch = read_output_rch(txtinout, pollutant)
    agg = rch.groupby("SUB").agg(TOT_load=("TOT_load", "mean")).reset_index()
    df = subattr.merge(agg, on="SUB", how="left")
    df["target_load"] = df["TOT_load"] / df["Area_ha"].replace(0, np.nan)
    feats = [c for c in ["Slope_pct", "Elev_m", "Area_ha"] if c in df.columns]
    return df, feats, "target_load"


def screen_factors(scenario_dir: str, txtinout: str, pollutant: Pollutant,
                   subattr: pd.DataFrame, n_boot: int = 200,
                   mi_thresh: float = 0.05, rho_thresh: float = 0.3,
                   random_state: int = 42) -> pd.DataFrame:
    """MI + Spearman 相关筛选，返回每个候选因子一行的得分表。

    列：feature, MI_Score, Spearman_Corr, Spearman_p, Boot_Selected_Freq, Selected, Direction
    """
    from scipy.stats import spearmanr
    from sklearn.feature_selection import mutual_info_regression

    df, feats, target = _build_feature_table(scenario_dir, txtinout, pollutant, subattr)
    if not feats:
        return pd.DataFrame(columns=["feature", "MI_Score", "Spearman_Corr",
                                     "Spearman_p", "Boot_Selected_Freq",
                                     "Selected", "Direction"])

    X = df[feats].fillna(0.0)
    y = df[target].fillna(0.0)

    mi = pd.Series(mutual_info_regression(X, y, random_state=random_state), index=feats)
    rho, pval = {}, {}
    for c in feats:
        r, p = spearmanr(X[c], y)
        rho[c] = float(r) if np.isfinite(r) else 0.0
        pval[c] = float(p) if np.isfinite(p) else 1.0
    rho = pd.Series(rho)
    pval = pd.Series(pval)

    # bootstrap 稳定性：重采样子流域，统计每个因子被选中的频率
    import warnings as _w
    rng = np.random.default_rng(random_state)
    sel_count = pd.Series(0, index=feats)
    n = len(df)
    if n >= 5:
        with _w.catch_warnings():
            _w.simplefilter("ignore")  # 重采样可能令某因子恒定，spearman 警告无害
            for _ in range(n_boot):
                idx = rng.integers(0, n, n)
                Xb, yb = X.iloc[idx], y.iloc[idx]
                try:
                    mib = pd.Series(mutual_info_regression(Xb, yb, random_state=random_state), index=feats)
                except Exception:
                    continue
                for c in feats:
                    rb, _ = spearmanr(Xb[c], yb)
                    if (mib[c] > mi_thresh) and (abs(rb) > rho_thresh if np.isfinite(rb) else False):
                        sel_count[c] += 1
    boot_freq = sel_count / max(n_boot, 1)

    selected = (mi > mi_thresh) & (rho.abs() > rho_thresh)
    direction = pd.Series(["negative" if rho[c] < 0 else "positive" for c in feats], index=feats)

    out = pd.DataFrame({
        "feature": feats,
        "MI_Score": mi.values,
        "Spearman_Corr": rho.values,
        "Spearman_p": pval.values,
        "Boot_Selected_Freq": boot_freq.values,
        "Selected": selected.values,
        "Direction": direction.values,
    }).sort_values("MI_Score", ascending=False).reset_index(drop=True)
    return out


# ============================================================================
# 2) 阈值标定（三模式）
# ============================================================================
def calibrate_thresholds(factors: List[FactorSpec], subattr: pd.DataFrame,
                         method: str = "swat_quantile",
                         quantile: float = 0.5,
                         manual: Optional[Dict[str, float]] = None,
                         monitoring: Optional[Dict[int, pd.DataFrame]] = None,
                         ) -> Calibration:
    """为每个因子确定阈值，返回新的 Calibration（含 provenance）。

    - 'swat_quantile' : 阈值 = 该因子在各子流域上的分位数（默认中位数），标 provisional。
    - 'manual'        : 用 manual={name: value} 覆写。
    - 'monitoring_roc': 若提供 per-subbasin 监测标签，用 Youden 求最优切点；
                        否则退回分位数并仅用监测时间序列做 validate_standard（AUC）。
    """
    manual = manual or {}
    new_factors: List[FactorSpec] = []
    for f in factors:
        col = f.name
        vals = subattr[col].dropna().values if col in subattr.columns else np.array([])
        thr = f.threshold
        prov = f.provenance

        if method == "manual" and col in manual:
            thr, prov = float(manual[col]), "manual"
        elif method == "monitoring_roc" and monitoring and col in (monitoring.get("labels", {}) or {}):
            thr = _youden_threshold(monitoring["labels"][col]["x"], monitoring["labels"][col]["y"])
            prov = "monitoring_roc"
        else:  # swat_quantile 或 monitoring 无空间标签 -> 分位数退回
            if len(vals):
                thr = float(np.quantile(vals, quantile))
                prov = "swat_quantile"
        new_factors.append(FactorSpec(col, f.direction, thr, prov))

    calib = Calibration(factors=new_factors, mode=method)
    if method == "swat_quantile":
        calib.notes = f"SWAT 分位数启发式（q={quantile}），provisional，建议获取监测后重标定。"
    return calib


def _youden_threshold(x: np.ndarray, y: np.ndarray) -> float:
    """对连续因子 x 与二分类标签 y 用 Youden's J 找最优切点。"""
    from sklearn.metrics import roc_curve
    x = np.asarray(x, float)
    y = np.asarray(y, int)
    if len(np.unique(y)) < 2:
        return float(np.median(x))
    fpr, tpr, thr = roc_curve(y, x)
    j = tpr - fpr
    return float(thr[int(np.argmax(j))])


# ============================================================================
# 3) 有效性验证（复刻 CRS-ACM 说明书：AUC / 准确率 / 特异度）
# ============================================================================
def validate_standard(monitoring: pd.DataFrame,
                      conc_col: str = "TN",
                      bio_col: str = "Algae",
                      bloom_threshold: float = 400.0,
                      static_standards: Optional[List[float]] = None,
                      ) -> Dict:
    """时滞对齐 + 二分类验证。

    monitoring 需含列 [Month, <conc_col>, <bio_col>]。
    返回 {'auc_dynamic': ..., 'static': {std: {accuracy, specificity, auc}}}。
    """
    from sklearn.metrics import roc_auc_score, accuracy_score, confusion_matrix

    df = monitoring.copy().sort_values("Month").reset_index(drop=True)
    df["conc_lag"] = df[conc_col].shift(1)
    df = df.dropna(subset=["conc_lag", bio_col])
    if df.empty:
        return {"auc_dynamic": float("nan"), "static": {}}

    y_true = (df[bio_col] > bloom_threshold).astype(int).values
    result: Dict = {"static": {}}

    # 动态体系：用连续滞后浓度作为打分
    try:
        result["auc_dynamic"] = float(roc_auc_score(y_true, df["conc_lag"].values)) \
            if len(np.unique(y_true)) > 1 else float("nan")
    except ValueError:
        result["auc_dynamic"] = float("nan")

    for std in (static_standards or [0.2, 0.5, 1.0, 1.5, 2.0]):
        y_pred = (df["conc_lag"].values > std).astype(int)
        acc = float(accuracy_score(y_true, y_pred))
        try:
            tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
            spec = float(tn / (tn + fp)) if (tn + fp) > 0 else float("nan")
        except ValueError:
            spec = float("nan")
        try:
            auc = float(roc_auc_score(y_true, y_pred)) if len(np.unique(y_true)) > 1 else 0.5
        except ValueError:
            auc = 0.5
        result["static"][std] = {"accuracy": acc, "specificity": spec, "auc": auc}
    return result


def _find_first(paths: List[str]) -> Optional[str]:
    for p in paths:
        if os.path.isfile(p):
            return p
    return None
