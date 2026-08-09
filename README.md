# WEC-Risk Platform · 水环境容量与风险评估集成平台

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Python](https://img.shields.io/badge/Python-3.12-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)
![GUI](https://img.shields.io/badge/GUI-PyQt5%20%2B%20Leaflet-orange.svg)
![Status](https://img.shields.io/badge/status-research%20release-brightgreen.svg)

> An integrated desktop tool that turns a built **SWAT2012** project into water environmental
> capacity & two-class pollution-risk maps — **bilingual (中文 / English)**, interactive, and
> transferable in principle, subject to basin-specific parameterization, calibration, and validation.
> Released as the research interface accompanying the associated paper.
>
> 一款把已建 **SWAT2012** 工程一键转化为水环境容量与两类污染风险地图的桌面程序——中英双语、
> 交互式；跨流域使用必须重新参数化、率定与验证，不能直接套用密云参数。

**Pipeline / 集成流程:**
SWAT outputs → key-factor screening → dynamic adaptive standard (CRS-ACM) → base & actual water
environmental capacity → two-class risk (local **LP** / upstream-transport **TR**) → high-risk areas
& transmission hotspots → **interactive map**.

---

## 📑 Contents
[Features](#-features--功能) · [Screenshots](#-screenshots--界面预览) · [Quick start](#-quick-start--快速开始) ·
[Structure](#-repository-structure--目录结构) · [Example data](#️-example-data--示例数据) ·
[SWAT prerequisite](#-swat-prerequisite--swat-前置) · [Methodology](#-methodology--方法学与公式) ·
[Citation](#-citation--引用) · [License & Patent](#-license--patent--许可证与专利) · [Manuals](#-manuals--详细手册)

---

## ✨ Features / 功能

- **Two mutually-exclusive risk indices** — Risk-1 (local) `LP = corrected NPS / W_actual`;
  Risk-2 (upstream transport) `TR = upstream inflow / W_actual`. 两类互不重叠的风险指数。
- **Interactive Leaflet map** — click a subbasin → dynamic standard, base/actual capacity, both
  risk classes; switchable thematic layers; **prominent transmission hotspots**; topology flow arrows.
- **Bilingual UI + global base maps** — OpenStreetMap (local), CartoDB Voyager/Positron (English),
  Esri Satellite; live language switch (中文 ⇄ English).
- **Per-year analysis** with user-selectable **spin-up years (NYSKIP)**; actual capacity & risk are
  produced **only for years that have point-source data**.
- **Multi-watershed workflow** — auto-detects common SWAT2012 layouts; transfer still requires
  basin-specific parameterization, threshold estimation, and validation;
  **pollutant interfaces for TN / TP / COD**.
- **Auditable factor and threshold workflow** — strict monthly parsing, a 31-river-sub-basin
  Spearman/BH-FDR/NMI screen, configured ROC·Youden estimates, and explicit provenance. The
  biological module is a fixed-threshold exploratory external comparison, not threshold tuning.
- **Auditable research release** — the final-revision derived tables are under
  [`paper_revision/results/`](paper_revision/results/), with provenance and redistribution limits in
  [`DATA_PROVENANCE.md`](DATA_PROVENANCE.md). The public example is configured, not calibrated.

## 🖼 Screenshots / 界面预览

![Interactive risk map — Miyun example, Risk-2 (TR) layer with transmission hotspots](docs/screenshot_map.png)

> **WEC-Risk Platform v1.0 — interactive map tab.** Click any subbasin to see its dynamic standard,
> base/actual capacity and both risk classes; the Risk-2 (upstream-transport, **TR**) layer highlights
> transmission **hotspots** (red markers). 交互地图页：点击子流域查看其动态标准、基础/实际容量与两类
> 风险；第二类（上游传输 **TR**）风险图层突出显示传输**热点**（红色标记）。

## 🚀 Quick start / 快速开始

**From source / 源码运行**
```bash
pip install -r requirements.txt
python main.py                       # GUI — menu: Project ▸ "Load Miyun example"
# headless reconcile against the published numbers:
python main.py --cli --project examples/miyun_project.json --year 2022 --reconcile
```

**Windows .exe / 打包可执行文件**
```bat
build_exe.bat                        REM -> dist\WEC_Platform\WEC_Platform.exe (self-contained, with example data)
```

> ⚠️ **Do not commit `build/` or `dist/`** (≈0.5 GB, already in `.gitignore`). Distribute the `.exe`
> via a GitHub *Release* asset or cloud drive — the repository ships **source + a 7 MB example only**.

## 📦 Repository structure / 目录结构

```
.
├── main.py                       # entry point (GUI / --cli)
├── requirements.txt
├── build_exe.bat · wec_platform.spec
├── LICENSE · NOTICE · CITATION.cff · .gitignore
├── README.md · README_中文.md · README_English.md
├── wec_platform/                 # source package
│   ├── config.py project.py swat_io.py swat_runner.py
│   ├── calibration.py pipeline.py geo.py mapview.py i18n.py
│   └── ui/  (main_window, panels, charts, state, bridge, style)
├── examples/
│   ├── miyun_project.json        # portable example project (relative paths)
│   └── monitoring_template.csv   # optional external-comparison format (Year, Month, TN, Algae)
├── docs/                         # put screenshots / extra docs here
└── data/Miyun/                   # bundled example (Miyun Reservoir basin, analysis-ready subset)
    ├── Watershed/Shapes/{subs1,riv1}.*
    ├── Scenarios/Miyun_Calib_01/TxtInOut/{file.cio,fig.fig,output.rch,output.sub}
    ├── Scenarios/Miyun_Calib_01/subbasin_water_quality_standards.csv  (+ extract_*.csv)
    ├── factor_screening_frame_final.csv   # derived 31-row canonical screening frame
    └── PL_Point_TN_{2020,2021,2022}.csv
```

## 🗺️ Example data / 示例数据

`data/Miyun/` holds **analysis-ready configured outputs** from a SWAT2012 model of the Miyun
Reservoir basin (31 river sub-basins plus reservoir node 32). No compatible observed flow-and-TN
series or SWAT-CUP archive was found, so the example must not be described as calibrated. It is
sufficient to demonstrate the interface; the full weather/HRU project and licensed third-party
inputs are intentionally not included. See [`DATA_PROVENANCE.md`](DATA_PROVENANCE.md).

示例 `data/Miyun/` 仅含 SWAT **已配置、未完成可靠联合率定**的分析输出。它用于演示界面和相对诊断，
不能作为监管或工程设计的绝对依据；完整天气/HRU工程与受许可约束的第三方原始数据不随仓库分发。

## 🔬 SWAT prerequisite / SWAT 前置

Watershed delineation, HRU definition and weather writing are performed in **QSWAT / ArcSWAT**;
this tool reads the **model outputs** (`output.rch`, `output.sub`, `file.cio`, `fig.fig`) plus the
subbasin/river shapefiles. Minimum file set and data formats are in the manuals.

流域划分、HRU 定义与天气写入在 **QSWAT** 中完成；本工具读取其输出与矢量。最小文件集见手册。

## 📐 Methodology / 方法学与公式

| Step | Formula (faithful to the validated scripts) |
|---|---|
| Spatially adaptive benchmark | `alpha = sum(w_f*s_f)/sum(w_f)`; `C_dynamic = C_strict + alpha*(C_loose-C_strict)` unless an already-compliant/protected-node gate retains `C_strict` |
| Base capacity | `Wi = a·[86.4·Q·(C_it − C_up) + 1e-3·K·V·C_it]` (negative capacity retained; mass-weighted conc.) |
| Retention | `R_tilde = (IN_river + NPS + point − OUT)/(IN_river + NPS + point)`; `R = min(1,max(0,R_tilde))` |
| Actual capacity | `W_actual = Wi − that-year point source` |
| Risk-1 / Risk-2 | `LP = corrected NPS/W_actual`, `TR = upstream inflow/W_actual`, both only when `W_actual > 0`; deficit nodes are classified directly |

- The paper-revision factor screen uses 31 river sub-basins, BH-FDR, quartile-binned NMI, and 5,000
  bootstrap replicates. Terrain thresholds are modest-discrimination, basin-specific operational
  estimates from the configured model; they are not strong predictors or statutory replacements.
- The elevation threshold change from 284.55 to 330.60 m is traced to removal of the non-comparable
  reservoir node from the river ROC population. See the
  [controlled threshold audit](paper_revision/THRESHOLD_CHANGE_AUDIT.md) and the
  [implementation map](paper_revision/IMPLEMENTATION.md).

## 📚 Citation / 引用

If you use this software, please cite **both** the software and the paper. Citation metadata is in
[`CITATION.cff`](CITATION.cff) (GitHub shows a *"Cite this repository"* button). BibTeX template:

```bibtex
@software{wecrisk_platform_2026,
  author  = {Sun, Haiming},
  title   = {WEC-Risk Platform: SWAT-based water environmental capacity and two-class risk assessment},
  year    = {2026},
  version = {1.0},
  url     = {https://github.com/Hai-mian-33/WEC-Risk-Platform},
  license = {MIT}
}
% Accepted conference paper; add proceedings pages and DOI when assigned:
@inproceedings{wecrisk_paper_2026,
  author  = {Sun, Haiming},
  title   = {A Capacity--Risk--Standard Adaptive Coupling Model (CRS-ACM) for Spatially Differentiated Watershed Water-Quality Management: A Case Study of Total Nitrogen in the Miyun Reservoir Basin},
  booktitle = {Proceedings of WREM 2026},
  year    = {2026},
  note    = {Accepted; publication details pending}
}
```

## ⚖️ License & Patent / 许可证与专利

- **Software code: [MIT License](LICENSE).** Free to use, modify and redistribute with attribution.
- **Pending application:** a Chinese invention patent application related to CRS-ACM
  (Application No. 202610879952.8) was filed by Tsinghua University on 17 June 2026. It is pending
  and is not a granted patent. The MIT License permits use, modification, distribution,
  sublicensing, and sale of copies of the software under its copyright terms; its text does not
  provide an express patent license. See [`NOTICE`](NOTICE). This repository does not determine
  whether a particular implementation practices any eventual patent claim; obtain legal advice if
  that question matters to your use.
- **Binary redistribution note:** the bundled `.exe` includes **PyQt5 (GPL)**. Distributing the
  source under MIT is unaffected, but redistributing the built binary must comply with PyQt5's GPL
  terms (or use a commercial Qt license). 见 `NOTICE`。

> ℹ️ The paper has been accepted by WREM 2026. Proceedings volume, page range, and DOI will be added
> to `CITATION.cff` when assigned.

## 📖 Manuals / 详细手册

- **中文使用说明：[README_中文.md](README_中文.md)**
- **English manual: [README_English.md](README_English.md)**

## 🙏 Acknowledgements / 致谢

Built on SWAT (USDA-ARS / Texas A&M), QSWAT, and the open-source Python geospatial stack
(geopandas, shapely, pyproj, pyogrio), PyQt5, Leaflet/folium, and base maps © OpenStreetMap
contributors, © CARTO, and Esri.
