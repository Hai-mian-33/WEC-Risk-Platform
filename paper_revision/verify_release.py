"""Fast cross-file checks for the public camera-ready release."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "paper_revision" / "results"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    factor_frame = pd.read_csv(ROOT / "data" / "Miyun" / "factor_screening_frame_final.csv")
    factors = pd.read_csv(RESULTS / "factor_screening_results.csv")
    roc = pd.read_csv(RESULTS / "roc_bootstrap_results.csv").set_index("feature")
    benchmarks = pd.read_csv(RESULTS / "adaptive_benchmark_results.csv")
    capacity = pd.read_csv(RESULTS / "capacity_risk_results.csv")
    validation = pd.read_csv(RESULTS / "validation_results.csv")
    sensitivity = pd.read_csv(RESULTS / "sensitivity_results.csv")

    require(len(factor_frame) == 31 and 32 not in set(factor_frame["SUB"]),
            "canonical factor frame must contain 31 river sub-basins and exclude node 32")
    require((factors["n"] == 31).all(), "factor table n must be 31")
    retained = set(factors.loc[factors["role"] == "Benchmark terrain factor", "feature"])
    require(retained == {"Slope_pct", "Elev_m"}, "unexpected benchmark factor set")
    require(abs(roc.loc["Slope_pct", "youden_threshold"] - 19.152642394642903) < 1e-10,
            "slope threshold mismatch")
    require(abs(roc.loc["Elev_m", "youden_threshold"] - 330.604511386437) < 1e-10,
            "elevation threshold mismatch")
    require((roc["n_monthly_records"] == 4092).all(), "ROC must use 31 x 132 records")
    require(len(benchmarks) == 32 and len(capacity) == 32, "benchmark/capacity tables must have 32 nodes")
    reservoir = benchmarks.loc[benchmarks["SUB"] == 32]
    require(len(reservoir) == 1 and bool(reservoir.iloc[0]["CORE_PROTECTION_GATE"]),
            "reservoir protection gate is missing")
    pooled = validation[validation["period"].astype(str).str.lower() == "pooled"]
    require((pooled["n"] == 33).all(), "pooled ecological comparison must report n=33")
    dynamic = pooled[pooled["rule"].str.startswith("Dynamic")]
    require(len(dynamic) == 1 and abs(dynamic.iloc[0]["threshold_mg_l"] - 1.0720626941503875) < 1e-12,
            "fixed dynamic ecological threshold mismatch")
    require("signed_deficit_sum_kg_d" in sensitivity and
            "total_deficit_magnitude_kg_d" in sensitivity,
            "deficit sign convention columns are missing")
    require(not (RESULTS / "validation_raw_pairs.csv").exists(),
            "restricted row-level ecological pairs must not be published")
    print("Release verification passed: thresholds, populations, gates, signs, and data boundary are consistent.")


if __name__ == "__main__":
    main()
