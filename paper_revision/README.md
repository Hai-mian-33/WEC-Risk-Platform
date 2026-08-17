# WR26-014 derived results

This directory contains selected non-restricted, machine-readable outputs associated with the publication version of WR26-014.

The tables were generated with random seed `20260809` from the local reproducibility workflow. They are provided to make reported values auditable; they do not replace the unavailable licensed inputs and do not establish SWAT calibration.

Included result groups:

- corrected 31-sub-basin factor screening with BH-FDR and 5,000 bootstrap replicates;
- cluster-bootstrap ROC estimates;
- 32-node adaptive benchmark and capacity-risk diagnostics;
- nonlinear-score and one-at-a-time sensitivity summaries;
- S1-S9 scenario summaries and nitrogen-response diagnostics;
- aggregated exploratory ecological-validation metrics.

The S1-S4 and S9 publication scenarios use fertilizer product ID 4 (urea)
for the six agricultural HRUs in sub-basin 31. Product applications of 100
and 150 kg ha^-1 correspond to 46 and 69 kg mineral N ha^-1, respectively.
The paired files `publication_bmp_scenario_results.csv` and
`publication_urea_nitrogen_diagnostics.csv` report the scenario-comparative
TN results and the corresponding nitrogen responses used in the paper.

The interactive WEC-Risk example continues to use the baseline data package.
Its interface, colour scheme, and interaction design are unchanged; the files
in this directory provide publication results rather than changing the example
case displayed by the program.

Additional camera-ready audit tables document NMI bootstrap behavior,
parameter evidence status, reservoir-cap activation, ecological-source
provenance, and scenario-file hashes. See
[`THRESHOLD_CHANGE_AUDIT.md`](THRESHOLD_CHANGE_AUDIT.md) for the controlled
old/new threshold reproduction and [`IMPLEMENTATION.md`](IMPLEMENTATION.md)
for the mapping from the paper workflow to the interactive code.

Raw ecological pairs, original point-source rasters, meteorological forcing, and third-party monitoring files are intentionally excluded. See [`../DATA_PROVENANCE.md`](../DATA_PROVENANCE.md).
