from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from wec_platform import swat_io
from wec_platform.calibration import screen_factors, validate_standard
from wec_platform.project import Project


ROOT = Path(__file__).resolve().parents[1]


class FinalRevisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project = Project.load(str(ROOT / "examples" / "miyun_project.json"))

    def test_strict_rch_monthly_population(self):
        cio = swat_io.read_file_cio(self.project.txtinout)
        rch = swat_io.read_output_rch(
            self.project.txtinout, self.project.pollutant, cio=cio,
        )
        self.assertEqual(len(rch), 32 * 132)
        self.assertEqual(rch["SUB"].nunique(), 32)
        self.assertTrue((rch.groupby("SUB").size() == 132).all())
        self.assertEqual((int(rch["YEAR"].min()), int(rch["YEAR"].max())), (2015, 2025))
        self.assertEqual(sorted(rch["MONTH"].unique()), list(range(1, 13)))

    def test_factor_screening_population_and_point_estimates(self):
        # A small bootstrap count keeps the unit test quick; point estimates
        # are independent of the number of replicates.
        result = screen_factors(
            self.project.scenario_dir,
            self.project.txtinout,
            self.project.pollutant,
            pd.DataFrame(),
            n_boot=50,
            random_state=20260809,
            canonical_frame=self.project.data_input_path("factor_screening_frame"),
            exclude_nodes=self.project.protection_nodes,
        ).set_index("feature")
        self.assertTrue((result["n"] == 31).all())
        self.assertAlmostEqual(result.loc["Slope_pct", "spearman_rho"], -0.5524193548387096)
        self.assertAlmostEqual(result.loc["Elev_m", "spearman_rho"], -0.6665322580645162)
        self.assertEqual(result.loc["Slope_pct", "role"], "Benchmark terrain factor")
        self.assertEqual(result.loc["Elev_m", "role"], "Benchmark terrain factor")

    def test_archived_roc_thresholds(self):
        roc = pd.read_csv(ROOT / "paper_revision" / "results" / "roc_bootstrap_results.csv")
        values = roc.set_index("feature")
        self.assertTrue((roc["n_subbasins"] == 31).all())
        self.assertTrue((roc["n_monthly_records"] == 4092).all())
        self.assertAlmostEqual(values.loc["Slope_pct", "youden_threshold"], 19.152642394642903)
        self.assertAlmostEqual(values.loc["Elev_m", "youden_threshold"], 330.604511386437)

    def test_external_comparison_is_fixed_threshold(self):
        monitoring = pd.DataFrame({
            "Year": [2020] * 5 + [2021] * 5,
            "Month": list(range(1, 6)) * 2,
            "TN": [0.8, 1.2, 0.9, 1.4, 0.7, 0.7, 1.3, 0.8, 1.5, 0.6],
            "Algae": [100, 500, 100, 500, 100, 100, 500, 100, 500, 100],
        })
        result = validate_standard(monitoring, n_boot=50, random_state=20260809)
        dynamic = result["rules"]["Dynamic (fixed, pre-algae)"]
        self.assertEqual(result["n"], 8)  # first month in each year is lost to lagging
        self.assertAlmostEqual(dynamic["threshold_mg_l"], 1.0720626941503875)
        self.assertEqual(result["bootstrap"]["design"], "year-stratified circular moving-block")
        self.assertFalse(np.isnan(dynamic["balanced_accuracy"]))


if __name__ == "__main__":
    unittest.main()
