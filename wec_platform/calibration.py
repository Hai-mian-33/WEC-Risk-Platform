"""Factor screening, threshold configuration, and external comparison.

The final-paper screen is a *configured-model association analysis*, not a
calibration claim or an independent causal discovery.  It uses one row per
actual river sub-basin, Spearman rho, BH-FDR, quartile-binned normalized
mutual information (NMI), and paired sub-basin bootstrap intervals.

Threshold configuration and ecological comparison are deliberately separate:
ROC/Youden estimates a basin-specific operational cut against a prespecified
binary outcome, whereas ecological data are used only for a fixed-threshold,
exploratory external comparison.
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
                         pollutant: Pollutant, subattr: pd.DataFrame,
                         canonical_frame: Optional[str] = None,
                         years: Optional[List[int]] = None,
                         exclude_nodes: Optional[List[int]] = None,
                         ) -> Tuple[pd.DataFrame, List[str], str]:
    """Build one auditable row per river sub-basin.

    A release may provide a canonical, derived factor frame containing all
    nine variables.  Otherwise the generic fallback uses strictly parsed
    ``output.rch`` plus DBF terrain attributes and reports the smaller set of
    variables actually available.  Legacy mixed ``extract_*.csv`` files are
    never used as monthly-analysis inputs.
    """
    target = "TN_LOAD_KG_HA_MONTH"
    if canonical_frame and os.path.isfile(canonical_frame):
        df = pd.read_csv(canonical_frame, encoding="utf-8-sig")
        if target not in df.columns:
            raise ValueError(f"Canonical factor frame lacks {target}: {canonical_frame}")
    else:
        from .swat_io import read_file_cio, read_output_rch
        cio = read_file_cio(txtinout)
        rch = read_output_rch(txtinout, pollutant, years=years, cio=cio)
        agg = rch.groupby("SUB", as_index=False)["TOT_load"].mean()
        agg = agg.rename(columns={"TOT_load": "TN_OUT_MEAN_MONTHLY_KG"})
        df = subattr.merge(agg, on="SUB", how="inner")
        df[target] = df["TN_OUT_MEAN_MONTHLY_KG"] / df["Area_ha"].replace(0, np.nan)
    excluded = {int(x) for x in (exclude_nodes or [])}
    if excluded:
        df = df[~df["SUB"].astype(int).isin(excluded)].copy()
    if df["SUB"].duplicated().any():
        raise ValueError("Factor frame must contain one row per sub-basin")
    feats = [c for c in CANDIDATE_FEATURES if c in df.columns]
    return df.reset_index(drop=True), feats, target


def _benjamini_hochberg(p_values: np.ndarray) -> np.ndarray:
    p = np.asarray(p_values, dtype=float)
    order = np.argsort(p)
    q = np.empty(len(p), dtype=float)
    previous = 1.0
    for pos in range(len(p) - 1, -1, -1):
        idx = order[pos]
        previous = min(previous, p[idx] * len(p) / (pos + 1))
        q[idx] = previous
    return q


def _quartile_edges(values: np.ndarray) -> np.ndarray:
    return np.unique(np.quantile(np.asarray(values, float), [0.25, 0.5, 0.75]))


def _quartile_bins(values: np.ndarray, edges: Optional[np.ndarray] = None) -> np.ndarray:
    values = np.asarray(values, float)
    return np.digitize(values, _quartile_edges(values) if edges is None else edges, right=True)


def _nmi_quartile(x: np.ndarray, y: np.ndarray,
                  x_edges: Optional[np.ndarray] = None,
                  y_edges: Optional[np.ndarray] = None) -> float:
    from sklearn.metrics import normalized_mutual_info_score
    return float(normalized_mutual_info_score(
        _quartile_bins(x, x_edges), _quartile_bins(y, y_edges),
    ))


def screen_factors(scenario_dir: str, txtinout: str, pollutant: Pollutant,
                   subattr: pd.DataFrame, n_boot: int = 5000,
                   random_state: int = 20260809,
                   canonical_frame: Optional[str] = None,
                   years: Optional[List[int]] = None,
                   exclude_nodes: Optional[List[int]] = None) -> pd.DataFrame:
    """Final-revision factor screen with FDR and paired bootstrap CIs."""
    from scipy.stats import spearmanr

    df, feats, target = _build_feature_table(
        scenario_dir, txtinout, pollutant, subattr,
        canonical_frame=canonical_frame, years=years,
        exclude_nodes=exclude_nodes,
    )
    if not feats:
        return pd.DataFrame()
    y = df[target].fillna(0.0).to_numpy(float)
    rows = []
    for pos, feature in enumerate(feats):
        x = df[feature].fillna(0.0).to_numpy(float)
        rho, p_value = spearmanr(x, y)
        x_edges, y_edges = _quartile_edges(x), _quartile_edges(y)
        point_nmi = _nmi_quartile(x, y, x_edges, y_edges)
        rng = np.random.default_rng(random_state + pos * 10007)
        rho_boot, nmi_boot = [], []
        for _ in range(n_boot):
            idx = rng.integers(0, len(df), len(df))
            xb, yb = x[idx], y[idx]
            if np.unique(xb).size < 2 or np.unique(yb).size < 2:
                continue
            rb = spearmanr(xb, yb).statistic
            if np.isfinite(rb):
                rho_boot.append(float(rb))
                nmi_boot.append(_nmi_quartile(xb, yb, x_edges, y_edges))
        rho_ci = np.quantile(rho_boot, [0.025, 0.975])
        nmi_ci = np.quantile(nmi_boot, [0.025, 0.975])
        rows.append({
            "feature": feature, "n": len(df),
            "spearman_rho": float(rho), "p_value": float(p_value),
            "nmi_quartile": point_nmi,
            "rho_ci_low": float(rho_ci[0]), "rho_ci_high": float(rho_ci[1]),
            "nmi_ci_low": float(nmi_ci[0]), "nmi_ci_high": float(nmi_ci[1]),
            "bootstrap_replicates": int(n_boot),
            "valid_bootstrap_replicates": len(rho_boot),
            # Backward-compatible display value for the unchanged v1.0 GUI.
            # It is recomputed from the same paired bootstrap replicates and
            # is not used to retain benchmark factors.
            "legacy_boot_selected_freq": float(np.mean(
                (np.abs(np.asarray(rho_boot, dtype=float)) > 0.3)
                & (np.asarray(nmi_boot, dtype=float) > 0.05)
            )),
        })
    out = pd.DataFrame(rows)
    out["fdr_q_value"] = _benjamini_hochberg(out["p_value"].to_numpy())
    out["fdr_significant_0_05"] = out["fdr_q_value"] <= 0.05
    roles = {
        "Slope_pct": ("Benchmark terrain factor", "Retained intrinsic terrain attribute"),
        "Elev_m": ("Benchmark terrain factor", "Retained intrinsic terrain attribute"),
        "AGRL_pct": ("Load-side pressure", "Anthropogenic pressure; cannot justify benchmark relaxation"),
        "URBN_pct": ("Load-side pressure", "Anthropogenic pressure; cannot justify benchmark relaxation"),
        "FRST_pct": ("Excluded—terrain redundancy", "Strongly associated with terrain; treated as redundant"),
    }
    out["role"] = [roles.get(f, ("Excluded—non-significant", "Not retained after FDR screening"))[0]
                   for f in out["feature"]]
    out["decision_reason"] = [roles.get(f, ("Excluded—non-significant", "Not retained after FDR screening"))[1]
                              for f in out["feature"]]
    out["Direction"] = np.where(out["spearman_rho"] < 0, "negative", "positive")
    out["Selected"] = out["role"].eq("Benchmark terrain factor")
    # Preserve the original interface schema while supplying the corrected
    # n=31/FDR/bootstrap results.  These aliases affect presentation only.
    out["MI_Score"] = out["nmi_quartile"]
    out["Spearman_Corr"] = out["spearman_rho"]
    out["Spearman_p"] = out["p_value"]
    out["Boot_Selected_Freq"] = out["legacy_boot_selected_freq"]
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
    - 'monitoring_roc': programmatic interface only; requires prespecified
                        per-subbasin binary labels for each factor. The GUI does
                        not misuse a reservoir time series for terrain ROC.
    """
    manual = manual or {}
    if method == "monitoring_roc" and not (monitoring and monitoring.get("labels")):
        raise ValueError(
            "monitoring_roc requires prespecified per-subbasin binary labels; "
            "a reservoir time series cannot be used for spatial terrain ROC"
        )
    new_factors: List[FactorSpec] = []
    for f in factors:
        col = f.name
        vals = subattr[col].dropna().values if col in subattr.columns else np.array([])
        thr = f.threshold
        prov = f.provenance

        if method == "manual" and col in manual:
            thr, prov = float(manual[col]), "manual"
        elif method == "monitoring_roc" and monitoring and col in (monitoring.get("labels", {}) or {}):
            thr = _youden_threshold(
                monitoring["labels"][col]["x"], monitoring["labels"][col]["y"],
                direction=f.direction,
            )
            prov = "monitoring_roc"
        else:  # swat_quantile 或 monitoring 无空间标签 -> 分位数退回
            if len(vals):
                thr = float(np.quantile(vals, quantile))
                prov = "swat_quantile"
        new_factors.append(FactorSpec(col, f.direction, thr, prov, f.weight))

    calib = Calibration(factors=new_factors, mode=method)
    if method == "swat_quantile":
        calib.notes = f"SWAT 分位数启发式（q={quantile}），provisional，建议获取监测后重标定。"
    return calib


def _youden_threshold(x: np.ndarray, y: np.ndarray,
                      direction: str = "positive") -> float:
    """对连续因子 x 与二分类标签 y 用 Youden's J 找最优切点。"""
    from sklearn.metrics import roc_curve
    x = np.asarray(x, float)
    y = np.asarray(y, int)
    if len(np.unique(y)) < 2:
        return float(np.median(x))
    score = -x if direction == "negative" else x
    fpr, tpr, thr = roc_curve(y, score, drop_intermediate=False)
    j = tpr - fpr
    best = np.flatnonzero(np.isclose(j, np.nanmax(j)))
    chosen = int(best[len(best) // 2])
    value = float(thr[chosen])
    return -value if direction == "negative" else value


# ============================================================================
# 3) Exploratory external ecological comparison (fixed thresholds)
# ============================================================================
def _classification_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Return the five prespecified binary metrics and a confusion matrix."""
    from sklearn.metrics import confusion_matrix, matthews_corrcoef

    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    sensitivity = tp / (tp + fn) if tp + fn else float("nan")
    specificity = tn / (tn + fp) if tn + fp else float("nan")
    precision = tp / (tp + fp) if tp + fp else float("nan")
    balanced_accuracy = ((sensitivity + specificity) / 2
                         if np.isfinite(sensitivity) and np.isfinite(specificity)
                         else float("nan"))
    mcc = (float(matthews_corrcoef(y_true, y_pred))
           if len(y_true) and len(np.unique(np.r_[y_true, y_pred])) > 1 else 0.0)
    return {
        "sensitivity": float(sensitivity),
        "specificity": float(specificity),
        "balanced_accuracy": float(balanced_accuracy),
        "precision": float(precision),
        "mcc": mcc,
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
    }


def _circular_block_indices(n: int, block_length: int,
                            rng: np.random.Generator) -> np.ndarray:
    """Draw exactly ``n`` circular moving-block indices."""
    picked: List[int] = []
    while len(picked) < n:
        start = int(rng.integers(0, n))
        picked.extend((start + step) % n for step in range(block_length))
    return np.asarray(picked[:n], dtype=int)


def validate_standard(monitoring: pd.DataFrame,
                      conc_col: str = "TN",
                      bio_col: str = "Algae",
                      bloom_threshold: float = 400.0,
                      static_standards: Optional[List[float]] = None,
                      dynamic_threshold: float = 1.0720626941503875,
                      n_boot: int = 5000,
                      block_length: int = 3,
                      random_state: int = 20260809,
                      ) -> Dict:
    """Compare one fixed dynamic benchmark with five static class limits.

    This helper does not tune a threshold against algae labels.  It applies a
    one-month TN lag within year unless a precomputed ``TN_LAG_MG_L`` column is
    supplied, then reports pooled metrics with year-stratified, three-month
    circular moving-block bootstrap intervals.  The comparison is exploratory
    and is not evidence that the dynamic benchmark is ecologically superior.
    """
    df = monitoring.copy()
    year_col = "Year" if "Year" in df else ("YEAR" if "YEAR" in df else None)
    month_col = "Month" if "Month" in df else ("MONTH" if "MONTH" in df else None)
    if month_col is None:
        raise ValueError("Monitoring data require a Month or MONTH column")
    if year_col is None:
        year_col = "__year"
        df[year_col] = 0

    if "TN_LAG_MG_L" in df:
        df["conc_lag"] = pd.to_numeric(df["TN_LAG_MG_L"], errors="coerce")
    else:
        if conc_col not in df:
            raise ValueError(f"Monitoring data lack concentration column: {conc_col}")
        df = df.sort_values([year_col, month_col]).reset_index(drop=True)
        df["conc_lag"] = df.groupby(year_col)[conc_col].shift(1)
    if bio_col not in df and "ALGAE_10K_CELLS_L" in df:
        bio_col = "ALGAE_10K_CELLS_L"
    if bio_col not in df:
        raise ValueError(f"Monitoring data lack biological column: {bio_col}")
    df[bio_col] = pd.to_numeric(df[bio_col], errors="coerce")
    df = df.dropna(subset=["conc_lag", bio_col]).copy()
    if df.empty:
        return {"n": 0, "rules": {}, "bootstrap_ci": {}}

    rules = {"Dynamic (fixed, pre-algae)": float(dynamic_threshold)}
    for idx, std in enumerate(static_standards or [0.2, 0.5, 1.0, 1.5, 2.0], 1):
        rules[f"Static Class {['I', 'II', 'III', 'IV', 'V'][idx - 1]}"] = float(std)
    y_true = (df[bio_col].to_numpy(float) > bloom_threshold).astype(int)
    point: Dict[str, Dict[str, float]] = {}
    for label, threshold in rules.items():
        point[label] = _classification_metrics(
            y_true, (df["conc_lag"].to_numpy(float) > threshold).astype(int))
        point[label]["threshold_mg_l"] = threshold

    rng = np.random.default_rng(random_state)
    groups = [g.index.to_numpy() for _, g in df.groupby(year_col, sort=True)]
    boot = {label: {metric: [] for metric in
                    ["sensitivity", "specificity", "balanced_accuracy", "precision", "mcc"]}
            for label in rules}
    for _ in range(int(n_boot)):
        sampled = np.concatenate([
            idx[_circular_block_indices(len(idx), block_length, rng)] for idx in groups
        ])
        yt = (df.loc[sampled, bio_col].to_numpy(float) > bloom_threshold).astype(int)
        concentrations = df.loc[sampled, "conc_lag"].to_numpy(float)
        for label, threshold in rules.items():
            metrics = _classification_metrics(yt, (concentrations > threshold).astype(int))
            for metric in boot[label]:
                if np.isfinite(metrics[metric]):
                    boot[label][metric].append(metrics[metric])
    ci = {}
    for label, metrics in boot.items():
        ci[label] = {}
        for metric, values in metrics.items():
            ci[label][metric] = ([float(x) for x in np.quantile(values, [0.025, 0.975])]
                                 if values else [float("nan"), float("nan")])
    return {
        "n": int(len(df)), "positive_events": int(y_true.sum()),
        "rules": point, "bootstrap_ci": ci,
        "bootstrap": {
            "replicates": int(n_boot), "block_length_months": int(block_length),
            "design": "year-stratified circular moving-block",
            "seed": int(random_state),
        },
    }


def _find_first(paths: List[str]) -> Optional[str]:
    for p in paths:
        if os.path.isfile(p):
            return p
    return None
