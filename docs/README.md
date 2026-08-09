# docs/

Place figures and screenshots here, then reference them from the main `README.md`, e.g.:

```markdown
![Interactive risk map](docs/screenshot_map.png)
![Subbasin detail panel](docs/screenshot_detail.png)
```

Suggested figures for the paper-accompanying repo:
- `screenshot_map.png` — the interactive map with the transmission-hotspot overlay.
- `screenshot_detail.png` — a clicked subbasin showing dynamic standard / capacity / two risk classes.
- `method_flowchart.png` — the SWAT → screening → standard → capacity → risk pipeline.

把界面截图与论文配图放在此目录，并在根目录 `README.md` 中引用。

Data lineage, units, exclusions, and the configured-model limitations are documented in
[`../DATA_PROVENANCE.md`](../DATA_PROVENANCE.md). Selected final-revision derived tables are
archived under [`../paper_revision/results/`](../paper_revision/results/); restricted raw monitoring
and third-party source data are not redistributed.
