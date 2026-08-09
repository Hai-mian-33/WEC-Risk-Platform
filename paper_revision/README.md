# WREM 2026 final-revision results

This directory contains selected non-restricted, machine-readable outputs synchronized with the final revision of WR26-014.

The tables were generated with random seed `20260809` from the local reproducibility workflow. They are provided to make reported values auditable; they do not replace the unavailable licensed inputs and do not establish SWAT calibration.

Included result groups:

- corrected 31-sub-basin factor screening with BH-FDR and 5,000 bootstrap replicates;
- cluster-bootstrap ROC estimates;
- 32-node adaptive benchmark and capacity-risk diagnostics;
- nonlinear-score and one-at-a-time sensitivity summaries;
- S1-S9 configuration/output diagnostics;
- aggregated exploratory ecological-validation metrics.

Additional camera-ready audit tables document NMI bootstrap behavior,
parameter evidence status, reservoir-cap activation, ecological-source
provenance, and scenario-file hashes. See
[`THRESHOLD_CHANGE_AUDIT.md`](THRESHOLD_CHANGE_AUDIT.md) for the controlled
old/new threshold reproduction and [`IMPLEMENTATION.md`](IMPLEMENTATION.md)
for the mapping from the paper workflow to the interactive code.

Raw ecological pairs, original point-source rasters, meteorological forcing, and third-party monitoring files are intentionally excluded. See [`../DATA_PROVENANCE.md`](../DATA_PROVENANCE.md).
