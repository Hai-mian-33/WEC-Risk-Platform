## Summary

- aligns strict SWAT monthly parsing with the 2015–2025, 132-month analysis;
- excludes protected reservoir node 32 from the 31-river-sub-basin factor/ROC population;
- synchronizes FDR, NMI/bootstrap, threshold, benchmark, sensitivity, scenario, and ecological summary data;
- documents why the elevation threshold changed from 284.55 to 330.60 m;
- updates the GUI's screening and fixed-threshold external ecological comparison;
- clarifies configured-model, third-party data, MIT copyright-license, and pending-patent boundaries.

## Verification

- [ ] `python -m unittest discover -s tests -v`
- [ ] `python paper_revision/verify_release.py`
- [ ] `git diff --check`
- [ ] no restricted raw ecological pairs, rasters, forcing, credentials, or machine-local manifests

## Scientific scope

The public case is configured, not observationally calibrated. Derived
capacity and scenario outputs are diagnostic/model-derived estimates. The
ecological comparison is exploratory and reports no robust balanced-accuracy
advantage.
