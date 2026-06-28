# Water Environmental Capacity & Risk Platform (WEC-Risk) — User Manual (English)

> Version v1.0 · Bilingual (中文/English) · Default pollutant: Total Nitrogen TN (extensible to TP/COD)

Integrates a workflow previously scattered across QGIS, SWAT, ERA5_Workbench and dozens of scripts into
**one desktop application**: SWAT-run orchestration → key-factor screening → dynamic adaptive standard
(CRS-ACM) → base/actual water environmental capacity → two risk indices → high-risk areas / transmission
hotspots → interactive map. Any SWAT2012 project can be **auto-detected and loaded** (multi-watershed portability).

---

## 1. Install & Run

**Option A — the .exe (for end users)**
- Double-click `dist/WEC_Platform/WEC_Platform.exe`. The whole `WEC_Platform` folder is portable.

**Option B — from source (development)**
```bash
pip install -r requirements.txt
python main.py                      # GUI
python main.py --cli --project examples/miyun_project.json --year 2022 --reconcile   # headless / reconcile
```

**Language**: the menu **Language / 语言** switches between English ⇄ 中文 live.

---

## 2. Prerequisite — how far must SWAT modeling be taken?

This tool does **not** perform watershed delineation / HRU definition / weather writing (do those in QSWAT/ArcSWAT).
It reads results from a SWAT2012 project you have **already built and run**. In QSWAT, complete:

| Step | Manual? | Notes |
|---|---|---|
| 1. Delineation | ✅ in QSWAT | DEM → subbasins & streams → `Watershed/Shapes/subs1.shp`, `riv1.shp` |
| 2. HRU definition | ✅ **you define HRUs in QSWAT** | overlay CLCD land use, HWSD soil, slope bands. This tool does NOT create HRUs |
| 3. Weather data | ✅ import & write in QSWAT | feed precipitation/temperature to QSWAT's Weather Writer. **This tool does NOT need weather re-imported** — its effect is already in SWAT output |
| 4. Parameterize & Run SWAT | ✅ Run SWAT in QSWAT | must enable **monthly output** (IPRINT=monthly) → `Scenarios/<scenario>/TxtInOut/output.rch`, `output.sub` |
| 5. (optional) Calibration | as needed | if calibrated, point this tool at the calibrated scenario folder |

**Minimum file set this tool auto-detects:**
```
<project root>/
├── Watershed/Shapes/subs1.shp(.dbf/.prj/.shx)   # subbasin polygons (+ slope Slo1 / elev Elev / lat-lon)
├── Watershed/Shapes/riv1.shp(.dbf/...)          # river network (+ channel geometry Len2/Wid2/Dep2)
└── Scenarios/<scenario>/TxtInOut/
    ├── file.cio          # simulation period (IYR/NBYR/NYSKIP) -> output years inferred automatically
    ├── fig.fig           # river topology (upstream/downstream)
    ├── output.rch        # reach monthly output (flow, N-species fluxes)
    ├── output.sub        # subbasin monthly output (NPS generation)
    └── SWAT*.exe         # (optional) enables the in-app "Run SWAT" button
```

> **Weather data** is only needed during QSWAT modeling. After the SWAT run its effect is embedded in
> `output.rch/.sub`. **You do not import weather into this tool.**

---

## 3. Where to put data — auto-detected or manual?

| Data | Location | Detection | Format |
|---|---|---|---|
| DEM / CLCD / HWSD | anywhere (register path in tab ①) | **registration & validation only**; not used in computation (modeling done in QSWAT) | .tif / .mdb |
| SWAT project | pick the root folder | **auto-detected**: #subbasins, topology, area, projection, output years, channel geometry | QSWAT layout |
| **Point source** | project root **or** scenario folder | **auto-detected by filename**; or typed manually in tab ④ | see below |
| Standards table (optional) | root or scenario folder | auto-detected | see below |
| Monitoring data (calibration/validation) | anywhere | chosen manually in tab ③ | see below |

**Point-source file naming & format (important):**
- File name: `PL_Point_<pollutant>_<year>.csv`, e.g. `PL_Point_TN_2022.csv`.
- Columns: `Subbasin` (subbasin id), `PL_point_TN_g_s` (point-source flux in **g/s**).
  - ⚠️ The value **must be a flux in g/s**. If your source data is an annual load, convert with
    `g/s = kg_per_year ÷ (365 × 86400) × 1e3` (or `÷ (365 × 86400)` for g/year). **Do not mistake kg/yr for t/yr** (that inflates every value 1000×).
- The year is taken from the file name. **Only years that have their own point-source file** get an
  "actual capacity" and "risk" result (see §6).
- You may also type values (g/s) directly in the table on the left of tab ④ and click "Apply and recompute".

**Standards table `subbasin_water_quality_standards.csv`** (optional; if missing, all subbasins fall back to GB Class III):
- Must contain a subbasin-id column and a limit column (e.g. `TN标准限值(mg/L)`).
- Note: only the **limit value** is used as `C_strict`; **function-zone names are no longer displayed** (subbasins are shown by number — see §8).

---

## 4. Simulation years, spin-up & multi-year-average basis

- Tab ②'s "Simulation period & spin-up" box shows, parsed from `file.cio`: the **SWAT period** (e.g. 2008–2025),
  the **built-in spin-up NYSKIP** (e.g. 2008–2014, already skipped by SWAT — not in output), and the
  **output years available** (e.g. 2015–2025).
- **Spin-up must be an early contiguous block**: choose an **"Analysis start year"** — output years *before* it
  are excluded as extra spin-up; years *from* it onward feed the multi-year-average quantities (base capacity Wi,
  long-term concentration, NPS). E.g. choosing 2017 treats 2015–2016 as extra spin-up; analysis uses 2017–2025.
  This guarantees spin-up is early/contiguous (no accidental middle gap).
- The "→ years used for multi-year average" label updates live.
- Note: 2008–2014 (SWAT's NYSKIP spin-up) is not in the output and cannot be recovered here; to change it, edit
  NYSKIP in QSWAT and re-run SWAT. This tool only lets you *extend* spin-up into the output years.

## 4b. Map year dropdown & base maps

- Tab ④'s **year dropdown lists ALL output years** (not just the 3 with point source). Each year is tagged
  `✓point src` or `·std/cap only`:
  - Years with point source (2020/2021/2022): full display — dynamic standard, base/actual capacity, both risks, hotspots.
  - Years without point source: **only the dynamic adaptive standard and base capacity** are shown; switching to
    such a year auto-selects the "Dynamic standard" layer. Once you obtain that year's point source, enter it on
    the left and "Apply and recompute" to get its actual capacity and risk.
- **Transmission hotspots** are drawn on every layer as a **red dashed border** (legend at bottom-right).
- **Bilingual + global base maps**: the top-right layer control switches among multiple **global** base maps —
  OpenStreetMap (local-language/Chinese labels), CartoDB Voyager/Positron (English/Latin labels), and Esri
  Satellite (global). The default base map follows the UI language (zh→OSM, en→CartoDB Voyager), easing international use.

---

## 5. Calibration logic (thresholds, year scope, flow into the standard)

**Key-factor screening** (shown automatically in tab ③): MI + Spearman on SWAT-simulated data, with p-values and
bootstrap selection frequency — a driver analysis on a calibrated model.

**Three threshold-calibration modes** (set each factor's threshold T used in the dynamic standard):
1. **SWAT quantile (provisional)** — threshold = a quantile (median by default) of the factor across subbasins; no external data; labeled provisional.
2. **Monitoring ROC/Youden** — needs a monitoring CSV; Youden's J finds the optimal cut (most rigorous).
3. **Manual** — type thresholds directly in the factor table.

**Monitoring data format** (for ROC calibration & AUC validation):
- CSV with columns: `Month` (time order), `TN` (monthly concentration of the pollutant), `Algae` (biological response, e.g. algal cell density).
- Validation: TN is lag-aligned by 1 month; truth = `Algae > threshold`; the dynamic-system AUC and static
  baselines are computed — preserving the original "break the self-referential loop" rationale (the standard
  rule and the biological validator are independent).

**Apply scope (year-specific vs global) — answering "does calibrating with 2022 affect other years?"**
- Scope = **All years**: written to the global calibration; every year's dynamic standard updates.
- Scope = **Current year only**: written as a per-year calibration; **only the current year's** standard/capacity/risk changes — other years are untouched.
- So: select 2022, calibrate with 2022 data, choose "Current year only" → **only 2022 changes**; 2020/2021 stay the same. ✔

**How new thresholds flow into the new standard/capacity/risk (automatic & synchronized):**
clicking "Calibrate and refresh dynamic standard" recomputes, for the active year's calibration:
```
new thresholds → dynamic adaptive standard C_dynamic → base capacity Wi (targeting C_dynamic)
              → actual capacity → two risk indices / hotspots
```
The map, detail panel and charts refresh immediately — **no extra manual step needed**.

---

## 6. Point source & actual capacity (subtract only for years that have point data)

- Actual capacity `W_actual = base capacity Wi − that year's point load (kg/d)`, where `kg/d = g/s × 86.4`.
- **Only years with their own point-source file (or values you typed) get actual-capacity and risk results.**
- Years without point data (here 2015–2019, 2023–2025): **no actual capacity / risk output** — only the dynamic
  standard and base capacity are shown; the corresponding map layers are grey ("no data") and the detail panel notes this.
- The "Year" dropdown in tab ④ **lists only years that have point data** (here 2020/2021/2022).
- The NPS transport rate is computed with **that year's** point source too, so all quantities are internally consistent within a year.

---

## 7. The two risk indices (mutually exclusive)

- **Risk-1 (local)** `LP = corrected NPS flux / actual capacity` (Eq. 7).
- **Risk-2 (upstream transport)** `TR = upstream inflow flux Influx / actual capacity` (Eq. 8).
  - `Influx_i = Σ Outflux of upstream subbasins`; `Outflux_i = (Influx_i + local NPS + local point) × (1 − R_i)`.
- The numerators are "local" vs "imported from upstream" — **mutually exclusive**, enabling source attribution
  ("treat locally" vs "treat upstream").
- Classes: `<0 → V Overload (deficit) · ≤1 → I · ≤2 → II · ≤3 → III · else IV`.
- Transmission hotspot: Risk-2 ≥ class IV and import fraction (Influx/Outflux) ≥ 0.5.

---

## 8. Subbasin naming

- By default subbasins are shown **by number only** ("Subbasin 1", "Subbasin 2", …); the potentially confusing
  function-zone names are no longer displayed.
- Only key water bodies keep a name: here only **#32 = Miyun Reservoir**.
- To name other subbasins, add to `named_subbasins` in the project JSON: `{id: {"zh": "名称", "en": "Name"}}`.

---

## 9. Workflow (five tabs)

1. **① Project & Data** — pick SWAT root → "Auto-detect and create project"; register DEM/CLCD/HWSD/weather paths (record only); view summary & validation. Or "Load Miyun example".
2. **② Run & Analyze** — tick the simulation years for the multi-year average → "Run SWAT" (auto-chains Stage A if exe present) or "Run analysis pipeline (Stage A)".
3. **③ Calibrate & Validate** — view screening; pick mode + apply-scope to calibrate thresholds; import monitoring data for AUC.
4. **④ Interactive Map & Point Source** — edit point source (g/s) → "Apply and recompute"; switch layer/year; **click a subbasin** to see standard/capacity/both risks; hotspots & topology arrows overlaid.
5. **⑤ Overview Charts** — actual-capacity distribution, two-risk class distribution, dynamic vs strict standard, key-factor importance.

---

## 10. Core formulas (faithful to the validated scripts)

- Dynamic standard: `C_dynamic = C_strict + (C_loose − C_strict)·AdjIndex`, `C_loose = min(C_strict+1.0, 2.0)`
- Factor membership (negative): `x≥T→0; x≤0.5T→1; linear in between`
- Base capacity: `Wi = a·[86.4·Q·(C_it − C_up) + 1e-3·K·V·C_it]` (a=0.8, K=0.05; **no clipping of negative capacity**; mass-weighted concentration with optional cap; reservoir subbasins may set special K/V/C)
- Transport rate: `R = (IN_river + NPS + point − OUT)/(IN_river + NPS + point)`, using **that year's** point
- Actual capacity: `W_actual = Wi − that year's point`
- Risk: `LP = corrected NPS / W_actual`; `TR = Influx / W_actual`

> CLI `--reconcile` confirms `W_actual` and `LP` match the existing `risk_index_TN_2022_corrected.csv` column-by-column (max|Δ|≈1e-12).

---

## 11. Migrating to a new watershed (reuse)

The tool has **zero path hardcoding and auto-detects any SWAT2012 project**, so it **runs and maps**
on a new watershed out of the box. To obtain **scientifically valid** results, follow the "must-do
checklist" below — this is required by the methodology, not a limitation of the tool.

### What the tool does automatically
After *Auto-detect and create project* it reads: number of subbasins, river topology (`fig.fig`),
area, projection, output years (`file.cio`), channel geometry (`riv1.dbf`), subbasin attributes
(`subs1.dbf`). The whole pipeline and the pollutant (TN/TP/COD) are parameterized.

### ✅ Must-do checklist for a new watershed
1. **Build & run** the watershed's SWAT2012 project in QSWAT with **monthly output (IPRINT=monthly)**,
   producing `Watershed/Shapes/{subs1,riv1}.*` and
   `Scenarios/<scenario>/TxtInOut/{file.cio,fig.fig,output.rch,output.sub}` (min set in §2).
2. **Auto-detect and create project** — pick that project's root in tab ①.
3. **Add the watershed's standards table** (optional) `subbasin_water_quality_standards.csv` (per-subbasin
   limits); if missing, all subbasins fall back to GB Class III; column names are auto-guessed.
4. **Add point-source files** `PL_Point_<code>_<year>.csv` (columns `Subbasin, PL_point_<code>_g_s`, g/s);
   years without a point file show only the dynamic standard and base capacity (no actual capacity/risk).
5. **Recalibrate the dynamic-standard factor thresholds** (key): the Miyun thresholds (Slope 19.153 /
   Elev 284.546) are **Miyun-specific and must NOT be reused**. In tab ③, calibrate with the watershed's
   monitoring data via ROC/Youden (or the SWAT-quantile fallback, marked provisional).
6. **Configure region-specific corrections if needed**: if the watershed has a reservoir / extreme
   concentrations, manually set `conc_clip_upper` (concentration cap) and `reservoir_overrides`
   (reservoir subbasin K/V/target conc.) — see the boundary note below.
7. **Save project** → a `.wecproj.json`; reopen later via "Open project".

### ⚠️ Honest boundary note (Miyun-specific params never leak to other watersheds)
`detect()` contains a branch that applies Miyun-specific parameters **only when** the project name
contains "miyun" or the scenario is `Miyun_Calib_01`: concentration cap 7.0 mg/L, the SUB32 reservoir
special-case (K=0.025 / V=2e9 / C=1.0), and the "Miyun Reservoir" name (see `detect()` in
`wec_platform/project.py`).
- **Other watersheds do NOT trigger this branch** and get **generic defaults**: no concentration cap,
  no reservoir special-case, factor thresholds pending calibration — so **Miyun's parameters never
  leak into your watershed**.
- **Trade-off**: a new watershed's reservoir special-case and concentration cap must be **configured
  manually** (the tool does not auto-detect reservoir bodies). If your watershed has no large
  reservoir / extreme concentrations, keep the defaults.

---

## 12. FAQ

- **No basemap tiles?** OpenStreetMap tiles and the Leaflet library need internet; offline, subbasin polygons still render (only the basemap is missing).
- **Some years show no risk?** That year has no point-source file — by design, no actual capacity/risk is produced (§6).
- **Calibration didn't change values?** Make sure you clicked "Calibrate and refresh dynamic standard"; if you chose "Current year only", only the current year changes.
- **A few Chinese strings remain in English mode?** Text that is part of the data itself (e.g. from the standards table) is not translated; all UI labels are bilingual.

---

## 13. Citation

If you use this software in research, please cite **both** the software and the paper. Citation
metadata is in [`CITATION.cff`](CITATION.cff) (GitHub shows a "Cite this repository" button). BibTeX:

```bibtex
@software{wecrisk_platform_2026,
  author  = {Sun, Haiming},
  title   = {WEC-Risk Platform: SWAT-based water environmental capacity and two-class risk assessment},
  year    = {2026}, version = {1.0},
  url     = {https://github.com/Hai-mian-33/WEC-Risk-Platform}, license = {MIT}
}
% Peer-reviewed paper in preparation — switch to @article (add journal/volume/doi) on acceptance:
@unpublished{wecrisk_paper_2026,
  author = {Sun, Haiming}, title = {<Paper title>}, year = {2026}, note = {Manuscript in preparation}
}
```

## 14. License & Patent

- **Code:** released under the **MIT License** (see `LICENSE`) — free to use, modify and redistribute with attribution.
- **Patent:** the *method* implemented here (dynamic adaptive standard + base/actual water
  environmental capacity + two-class risk LP/TR) is covered by a separate patent / application held
  by the author (see `NOTICE`). **MIT covers the code only and grants no patent license**; using the
  patented method may require separate authorization from the patent holder.
- **Binary redistribution:** the bundled `.exe` includes **PyQt5 (GPL)**. Distributing the source
  under MIT is unaffected, but redistributing the built binary must comply with PyQt5's GPL terms
  (or use a commercial Qt license).

> Author, Chinese Patent Application No. (202610879952.8) and repository URL are filled in. The paper citation
> (title / journal / DOI) will be added to `CITATION.cff` and the BibTeX above once the manuscript is accepted.
