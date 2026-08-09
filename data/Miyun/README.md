# Miyun configured example

The bundled Miyun directory is an analysis-ready **configured SWAT2012 example** for the WEC-Risk interface. It is not a calibrated regulatory dataset.

- Analysis period for the paper revision: 2015-2025 (132 monthly records per modeled unit).
- Network: 31 river sub-basins plus protected Miyun Reservoir node 32.
- Point-source files: TN flux in g/s, recomputed from annual NH3-N rasters using calendar-year seconds and the disclosed operational ratios.
- Reservoir handling: the strict benchmark protection gate remains active; the 7 mg/L numerical cap applies only to inherited concentration at node 32; there is no basin-wide concentration clipping and no forced 1.0 mg/L reservoir target.
- Risk ratios: LP and TR are defined only when signed remaining capacity is positive; deficit nodes are classified directly as transmission- or local-source-driven.

For sources, redistribution boundaries, conversion equations, totals, and limitations, see [`../../DATA_PROVENANCE.md`](../../DATA_PROVENANCE.md).

