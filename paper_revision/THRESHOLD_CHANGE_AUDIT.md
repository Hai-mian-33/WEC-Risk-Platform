# Why the reported terrain thresholds changed

## Conclusion

The old values are reproducible from the old workflow, but that workflow did
not match the final analysis population. It treated node 32 (the protected,
mixed Miyun Reservoir node) as if it were an independent river sub-basin in
the ROC calculation. Its month filter also admitted one terminal summary row
per unit. The camera-ready workflow corrects both issues: factor screening and
ROC use the 31 actual river sub-basins and exactly 132 months from January 2015
through December 2025.

This is a methodological correction, not a change made to improve the result.
The slope threshold is unchanged, while the elevation threshold changes
because node 32 materially affected the location of the maximum Youden index.

## Controlled reproduction

| Calculation | Units | Monthly rows | Positive events | Slope AUC | Slope threshold (%) | Elevation AUC | Elevation threshold (m) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Legacy parser and legacy 32-node population | 32 | 4,256 | 1,841 | 0.593737 | 19.152642 | 0.607856 | 284.545548 |
| Legacy parser, but node 32 removed | 31 | 4,123 | 1,753 | 0.586466 | 19.152642 | 0.602248 | 330.604511 |
| Final strict parser and 31 river sub-basins | 31 | 4,092 | 1,723 | 0.586442 | 19.152642 | 0.602126 | 330.604511 |

The second row isolates population membership: removing node 32 alone moves
the elevation threshold to the final value. The third row isolates temporal
parsing and exact calendar-day weighting: it causes only small AUC changes and
does not move either Youden threshold.

## Why node 32 must be excluded here

Node 32 is retained in topology, benchmark gating, capacity, risk, and
reservoir-cap analyses. It is excluded only from cross-sectional river-factor
screening and ROC because it represents a protected reservoir mixing node,
not a comparable independent river sub-basin with the same interpretation of
terrain attributes and monthly routing response. Including it changes the
statistical population and conflicts with the stated 31-river-sub-basin
analysis design.

## Did the key-factor conclusion change?

No. Removing node 32 slightly changes the coefficients but does not overturn
the substantive factor roles. The corrected 31-sub-basin analysis retains
slope and elevation as benchmark terrain factors. Agriculture and urban cover
remain load-side pressures; forest remains strongly associated with terrain
and is treated as redundant; the remaining candidates are not retained after
BH-FDR correction. The analysis is described as model-consistent association,
not independent causal discovery.

## Interpretation

- The old elevation threshold is not the result of fabricated data; it is the
  result of an inconsistent analysis unit.
- For the intended river-sub-basin question, the old elevation threshold is
  not the defensible estimate and has been replaced by 330.604511 m.
- Both ROC AUC values show modest discrimination. The thresholds are
  basin-specific operational estimates, not universal physical thresholds.
- The bootstrap intervals are wide; transfer to another watershed requires
  recalculation rather than reuse of either value.

Machine-readable final estimates are in
[`results/roc_bootstrap_results.csv`](results/roc_bootstrap_results.csv), and
the corrected factor table is in
[`results/factor_screening_results.csv`](results/factor_screening_results.csv).
