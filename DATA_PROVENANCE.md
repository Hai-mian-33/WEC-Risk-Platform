# Data provenance and permitted use

This repository is a research-software release, not a complete calibrated SWAT project or a regulatory dataset.

## What is included

- `data/Miyun/Watershed/Shapes/`: case-study sub-basin and river geometry used by the interactive demonstration.
- `data/Miyun/Scenarios/Miyun_Calib_01/TxtInOut/`: selected **configured** SWAT2012 output files needed by the interface. The scenario name is historical; it is not evidence of a defensible flow-and-TN calibration archive.
- `data/Miyun/PL_Point_TN_2020.csv` to `PL_Point_TN_2022.csv`: sub-basin TN fluxes recomputed from the original urban and industrial NH3-N rasters.
- `paper_revision/results/`: selected non-restricted derived tables used in the WREM 2026 final revision.

The public case is intended to demonstrate parsing, visualization, and scenario-comparative diagnostics. Absolute loads, capacity values, and BMP effects are model-derived estimates and must not be treated as calibrated allocation permits or engineering design values.

## Point-source conversion

The source rasters store annual NH3-N load in kg/year. For each calendar year, the public sub-basin files were calculated as:

```text
urban TN (g/s)      = urban NH3-N (kg/year) x 1.30 x 1000 / seconds_in_year
industrial TN (g/s) = industrial NH3-N (kg/year) x 1.35 x 1000 / seconds_in_year
total TN (g/s)      = urban TN + industrial TN
```

The 1.30 and 1.35 factors are unpublished local operational assumptions, not universal measured ratios. The final-paper sensitivity analysis tests urban ratios 1.1/1.3/1.5 and industrial ratios 1.15/1.35/1.55. The corrected public totals are:

| Year | Urban TN (g/s) | Industrial TN (g/s) | Total TN (g/s) |
|---|---:|---:|---:|
| 2020 | 1.528965989 | 0.090192538 | 1.619158526 |
| 2021 | 1.459994069 | 0.072724315 | 1.532718384 |
| 2022 | 1.386557428 | 0.055199914 | 1.441757342 |

The former files affected by a tonnes/year-versus-kg/year factor of 1,000 are not used. Calendar-year seconds are used, including 366 days for 2020.

## What is not redistributed

This repository does not redistribute raw CMADS, ERA5-Land, the Yuan and Ma gridded discharge source, the original NH3-N rasters, or third-party ecological monitoring records. Obtain those inputs from their providers and follow their licenses and citation requirements. The `paper_revision/results/` directory contains derived summaries only; it intentionally excludes raw validation pairs and machine-local manifests.

## Temporal parsing

The final revision uses January 2015 through December 2025: exactly 132 monthly records per reach, sub-basin, and HRU. Annual summaries and terminal long-term-average rows are excluded. Historical `extract_rch.csv` and `extract_sub.csv` files remain only for backward compatibility with the v1.0 interface and must not be used as the final-paper monthly analysis input.

## Known limitations

- No compatible observed streamflow-and-TN series or SWAT-CUP/SUFI-2 archive was found for joint calibration and validation.
- A forcing-source transition from CMADS to ERA5-Land may introduce a structural discontinuity.
- The ecological reanalysis contains only 33 digitized monthly pairs and is exploratory.
- Basin-specific thresholds, protection nodes, decay parameters, and point-source assumptions must be recalibrated for any transfer.

