# Camera-ready analysis implementation

This note maps the final paper workflow to the public interactive program. It
is an implementation record, not a claim that the configured SWAT project was
observationally calibrated.

## Reproducible flow

1. `Project.load()` resolves the portable example and its registered derived
   inputs. The Miyun example declares 31 river sub-basins plus protected
   reservoir node 32.
2. `swat_io.read_output_rch()` and `read_output_sub()` use `file.cio` to keep
   exactly 12 ordered monthly rows per output year and per unit. Annual and
   terminal long-term summaries are rejected.
3. `pipeline.run_stage_a()` uses the selected 2015–2025 period and exact
   calendar-day volume weighting. It calls `screen_factors()` with seed
   `20260809`, 5,000 paired sub-basin bootstrap replicates, and protected nodes
   excluded from the screening population.
4. `calibration.screen_factors()` reports Spearman rho, two-sided p, BH-FDR q,
   quartile-binned NMI, and bootstrap intervals. NMI is supporting evidence;
   the role field records the scientific decision separately.
5. The example configuration stores the final low-direction ROC/Youden
   estimates: slope 19.152642% and elevation 330.604511 m. These are configured,
   basin-specific operational estimates with modest AUC, not fitted regulatory
   limits.
6. `pipeline.compute_dynamic_standard()` combines factor scores as a weighted
   mean. It does not apply cross-basin min-max stretching. Already-compliant
   and protected nodes retain their strict benchmark; the result is bounded
   relative to the GB class thresholds.
7. Capacity calculation retains signed `W`: negative values are node-level
   deficits. The reservoir concentration cap applies only to designated node
   32. Retention is clipped to [0, 1]. LP and TR are defined only for `W > 0`;
   deficit nodes are classified directly from local and upstream loads.
8. The interface exposes the latest factor table, dynamic benchmark, capacity,
   risk, and map layers. Its ecological helper compares a fixed pre-algae
   dynamic threshold with the five static class limits and uses a
   year-stratified, three-month circular moving-block bootstrap. It does not
   search algae labels for a favorable threshold.

## Public data boundary

The repository contains the canonical 31-row derived factor frame and selected
non-restricted result tables. It deliberately excludes original meteorological
forcing, NH3-N rasters, machine-local manifests, and the 33 third-party
graph-digitized ecological pairs. The latter remain subject to source and
redistribution constraints; only aggregated validation metrics and provenance
summaries are published.

## Key paths

| Purpose | Path |
|---|---|
| Portable example configuration | `examples/miyun_project.json` |
| Strict SWAT readers | `wec_platform/swat_io.py` |
| Factor screening and external comparison | `wec_platform/calibration.py` |
| Benchmark/capacity/risk orchestration | `wec_platform/pipeline.py` |
| Canonical derived factor frame | `data/Miyun/factor_screening_frame_final.csv` |
| Camera-ready derived outputs | `paper_revision/results/` |
| Threshold change audit | `paper_revision/THRESHOLD_CHANGE_AUDIT.md` |
| Data and redistribution statement | `DATA_PROVENANCE.md` |

## Reproduction and checks

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python paper_revision/verify_release.py
python main.py --cli --project examples/miyun_project.json --year 2022 --reconcile
```

The public program is a research implementation of an auditable watershed
diagnostic framework. Absolute loads, capacities, and BMP outcomes remain
model-derived and scenario-comparative.
