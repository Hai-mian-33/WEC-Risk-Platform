"""
panels.py — 各功能面板 / functional panels (bilingual)
=======================================================
ProjectPanel ① 工程与数据  CalibPanel ② 标定与验证  RunPanel ③ 运行
MapInteractPanel ④ 点源 + 交互地图 + 子流域详情（核心交互）
"""
from __future__ import annotations

import os
import tempfile

import pandas as pd
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QLineEdit, QFileDialog, QComboBox, QTableWidget, QTableWidgetItem,
    QGroupBox, QProgressBar, QMessageBox, QSplitter, QHeaderView,
    QDoubleSpinBox, QSpinBox, QPlainTextEdit, QTextEdit,
)

from .. import pipeline, i18n
from ..i18n import tr
from ..config import RISK_CLASS_COLORS, BUILTIN_POLLUTANTS
from ..mapview import LAYER_DEFS, layer_label, build_map_html
from ..project import Project, FactorSpec
from .charts import DetailMiniChart


# ============================================================================
# ① 工程与数据
# ============================================================================
class ProjectPanel(QWidget):
    def __init__(self, state, status_cb=None):
        super().__init__()
        self.state = state
        self.status_cb = status_cb or (lambda *_: None)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        g0 = QGroupBox(tr("工程", "Project"))
        f0 = QGridLayout(g0)
        self.root_edit = QLineEdit()
        self.root_edit.setPlaceholderText(tr(r"选择 SWAT 工程根目录（含 Watershed\ 与 Scenarios\）",
                                             r"Select SWAT project root (contains Watershed\ and Scenarios\)"))
        btn_browse = QPushButton(tr("浏览…", "Browse…"))
        btn_browse.clicked.connect(self._browse_root)
        btn_detect = QPushButton(tr("自动探测并新建工程", "Auto-detect and create project"))
        btn_detect.clicked.connect(self._detect)
        btn_open = QPushButton(tr("打开已有工程 (.wecproj.json)", "Open project (.wecproj.json)"))
        btn_open.clicked.connect(self._open)
        btn_save = QPushButton(tr("保存工程", "Save project"))
        btn_save.clicked.connect(self._save)
        f0.addWidget(QLabel(tr("工程根目录", "Project root")), 0, 0)
        f0.addWidget(self.root_edit, 0, 1)
        f0.addWidget(btn_browse, 0, 2)
        f0.addWidget(btn_detect, 1, 1)
        f0.addWidget(btn_open, 1, 2)
        f0.addWidget(btn_save, 2, 2)
        lay.addWidget(g0)

        gp = QGroupBox(tr("目标污染物", "Target pollutant"))
        fp = QHBoxLayout(gp)
        fp.addWidget(QLabel(tr("污染物", "Pollutant")))
        self.pollutant_combo = QComboBox()
        for code, pol in BUILTIN_POLLUTANTS.items():
            self.pollutant_combo.addItem(f"{pol.name_cn} / {code}", code)
        self.pollutant_combo.currentIndexChanged.connect(self._on_pollutant)
        fp.addWidget(self.pollutant_combo)
        fp.addWidget(QLabel(tr(
            "（TN 已完整验证；TP 映射 SWAT 磷输出；COD 为 CBOD 代理接口，需自备点源/标准/监测数据）",
            "(TN fully validated; TP maps SWAT P output; COD is a CBOD-proxy interface needing your "
            "own point-source/standards/monitoring data)")))
        fp.addStretch(1)
        lay.addWidget(gp)

        g1 = QGroupBox(tr("地理 / 气象数据登记（仅记录与校验，建模由 QSWAT 完成）",
                          "Geo / weather data registration (record & validate only; modeling done in QSWAT)"))
        f1 = QGridLayout(g1)
        self.data_edits = {}
        rows = [("dem", tr("DEM 高程 (.tif)", "DEM elevation (.tif)")),
                ("clcd", tr("CLCD 土地利用 (.tif)", "CLCD land use (.tif)")),
                ("hwsd", tr("HWSD 土壤 (.tif/.mdb)", "HWSD soil (.tif/.mdb)")),
                ("weather", tr("气象数据目录", "Weather data folder"))]
        for i, (key, label) in enumerate(rows):
            e = QLineEdit()
            b = QPushButton("…")
            b.setFixedWidth(40)
            b.clicked.connect(lambda _, k=key, lb=label: self._browse_data(k, lb))
            f1.addWidget(QLabel(label), i, 0)
            f1.addWidget(e, i, 1)
            f1.addWidget(b, i, 2)
            self.data_edits[key] = e
        lay.addWidget(g1)

        g2 = QGroupBox(tr("工程摘要 / 完整性校验", "Project summary / validation"))
        v2 = QVBoxLayout(g2)
        self.info = QPlainTextEdit()
        self.info.setReadOnly(True)
        v2.addWidget(self.info)
        lay.addWidget(g2, 1)
        self.state.projectChanged.connect(self._refresh_info)

    def _browse_root(self):
        d = QFileDialog.getExistingDirectory(self, tr("选择 SWAT 工程根目录", "Select SWAT project root"))
        if d:
            self.root_edit.setText(d)

    def _browse_data(self, key, label):
        if key == "weather":
            p = QFileDialog.getExistingDirectory(self, label)
        else:
            p, _ = QFileDialog.getOpenFileName(self, label)
        if p:
            self.data_edits[key].setText(p)
            if self.state.project:
                self.state.project.data_inputs[key] = p

    def _detect(self):
        root = self.root_edit.text().strip()
        if not root or not os.path.isdir(root):
            QMessageBox.warning(self, tr("提示", "Notice"), tr("请先选择有效的工程根目录。",
                                                              "Please select a valid project root first."))
            return
        try:
            proj = Project.detect(root)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, tr("探测失败", "Detection failed"), str(e))
            return
        for k, e in self.data_edits.items():
            if e.text().strip():
                proj.data_inputs[k] = e.text().strip()
        self.state.set_project(proj)
        self.status_cb(tr(f"已探测工程：{proj.name}", f"Project detected: {proj.name}"))

    def _open(self):
        p, _ = QFileDialog.getOpenFileName(self, tr("打开工程", "Open project"), "",
                                           "WEC (*.wecproj.json *.json)")
        if not p:
            return
        try:
            proj = Project.load(p)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, tr("打开失败", "Open failed"), str(e))
            return
        self.root_edit.setText(proj.root_dir)
        for k, e in self.data_edits.items():
            e.setText(proj.data_inputs.get(k, ""))
        self.state.set_project(proj)

    def _save(self):
        if not self.state.project:
            QMessageBox.warning(self, tr("提示", "Notice"), tr("尚无工程可保存。", "No project to save."))
            return
        default = os.path.join(self.state.project.root_dir, f"{self.state.project.name}.wecproj.json")
        p, _ = QFileDialog.getSaveFileName(self, tr("保存工程", "Save project"), default, "WEC (*.wecproj.json)")
        if p:
            path = self.state.project.save(p)
            self.status_cb(tr(f"工程已保存：{path}", f"Saved: {path}"))

    def _on_pollutant(self):
        proj = self.state.project
        if not proj:
            return
        code = self.pollutant_combo.currentData()
        pol = BUILTIN_POLLUTANTS.get(code)
        if not pol or code == proj.pollutant.code:
            return
        proj.pollutant = pol
        if code != "TN":   # TN/密云 专属的浓度截断与水库特例不适用其它污染物
            proj.conc_clip_upper = None
            proj.reservoir_overrides = {}
        self._refresh_info()
        self.status_cb(tr(f"目标污染物已切换为 {pol.name_cn}({code})；请重新运行阶段A，并提供该污染物的标准/点源数据。",
                          f"Pollutant switched to {code}; re-run Stage A and provide its standards/point-source data."))

    def _refresh_info(self):
        proj = self.state.project
        if not proj:
            return
        idx = self.pollutant_combo.findData(proj.pollutant.code)
        if idx >= 0:
            self.pollutant_combo.blockSignals(True)
            self.pollutant_combo.setCurrentIndex(idx)
            self.pollutant_combo.blockSignals(False)
        problems = proj.validate()
        L = [
            (tr("工程名称", "Project"), proj.name),
            (tr("根目录", "Root"), proj.root_dir),
            (tr("情景", "Scenario"), proj.scenario),
            (tr("污染物", "Pollutant"), tr(f"{proj.pollutant.name_cn} ({proj.pollutant.code})",
                                          proj.pollutant.code)),
            (tr("子流域数", "Subbasins"), proj.n_subbasins),
            (tr("输出年份", "Output years"), proj.years),
            (tr("SWAT 可执行", "SWAT exe"), proj.swat_exe or tr("未找到", "not found")),
            (tr("标准表", "Standards csv"), proj.standards_csv or tr("未找到(退回GB Ⅲ类)", "not found (fallback GB III)")),
            (tr("浓度截断", "Conc clip"), proj.conc_clip_upper),
            (tr("水库特例", "Reservoir overrides"), proj.reservoir_overrides or tr("无", "none")),
        ]
        lines = [f"{k:<10}: {v}" for k, v in L]
        lines.append("")
        lines.append(tr("标定因子:", "Calibration factors:"))
        for f in proj.calibration.factors:
            lines.append(f"   - {f.name}  dir={f.direction}  thr={f.threshold}  src={f.provenance}")
        lines.append("")
        lines.append(tr("完整性校验: ", "Validation: ") +
                     (tr("✔ 通过", "✔ OK") if not problems else tr("✘ 存在问题", "✘ issues")))
        for p in problems:
            lines.append("   · " + p)
        self.info.setPlainText("\n".join(lines))


# ============================================================================
# ② 标定
# ============================================================================
class CalibPanel(QWidget):
    def __init__(self, state, status_cb=None):
        super().__init__()
        self.state = state
        self.status_cb = status_cb or (lambda *_: None)
        self._build()
        state.stageAReady.connect(self._fill_screening)

    def _build(self):
        lay = QVBoxLayout(self)
        info = QLabel(tr(
            "<b>关键因子识别逻辑</b>："
            "① 先把 SWAT 的「子流域×月」数据<b>按子流域聚合为每单元一行</b>（n=子流域数，本例 32），"
            "再计算每个候选因子与 TN 产出的 <b>Spearman 单调相关 ρ（含 p 值）</b>与<b>互信息 MI</b>。"
            "② 因子识别<b>以 Spearman 单调相关（ρ 强、p 显著）+ 物理机制为主判据</b>；"
            "MI 仅作非线性依赖的<b>补充参考</b>（小样本截面下偏低且不稳，不作硬性门槛）。"
            "例如高程 Elev 以最强单调相关入选（ρ=−0.672, p&lt;0.001）。"
            "③ 动态标准只采用<b>坡度、高程</b>这两个负相关、代表稳定自然本底的地形因子"
            "（值越小→自净/缓冲能力越弱→标准适当放宽）；农用地、城镇等土地利用变量可被人为改变，"
            "不作为放宽依据。<br>"
            "④ 表中各列：『相关方向』正/负相关；『MI&ρ阈值(参考)』是否同时满足 MI&gt;0.05 且 |ρ|&gt;0.3"
            "（<b>仅供参考，不决定入选</b>）；<b>『用于动态标准』该因子是否真正参与标准计算——以此列为最终判断</b>。<br>"
            "<b>阈值标定模式</b>：「监测 ROC/Youden」用独立监测(藻细胞)求最优切点（本研究得 Slope=19.153、Elev=284.546）；"
            "「SWAT 分位数」为无监测时的退回方案（阈值取分位数 q=0.5 即中位数，标 provisional）。",
            "<b>Key-factor identification logic</b>: "
            "① Aggregate SWAT's 'subbasin × month' data to <b>one row per subbasin</b> "
            "(n = number of subbasins, here 32), then compute each candidate's <b>Spearman monotonic "
            "correlation ρ (with p-value)</b> and <b>mutual information MI</b> vs TN export. "
            "② Factors are identified <b>primarily by Spearman monotonic correlation (strong ρ, significant p) "
            "+ physical mechanism</b>; MI serves <b>only as a supplementary reference</b> for non-linear "
            "dependence (low and unstable on small cross-sections, not a hard threshold). E.g. elevation (Elev) "
            "enters by the strongest monotonic correlation (ρ=−0.672, p&lt;0.001). "
            "③ The dynamic standard uses only <b>Slope and Elev</b> — negatively-correlated terrain factors "
            "representing a stable natural baseline (smaller value → weaker self-purification → relax the "
            "standard); human-alterable land-use variables (cropland, urban, …) are not used as a basis. <br>"
            "④ Columns: 'Direction' = positive/negative; 'MI&ρ rule (ref.)' = whether MI&gt;0.05 AND |ρ|&gt;0.3 "
            "(<b>for reference only, does not decide selection</b>); <b>'Used in standard' = whether the factor "
            "actually drives the standard — this column is the final decision</b>.<br>"
            "<b>Threshold modes</b>: 'Monitoring ROC/Youden' finds the optimal cut against independent monitoring "
            "(algae; this study got Slope=19.153, Elev=284.546). 'SWAT quantile' is the no-monitoring fallback "
            "(threshold = quantile q=0.5 = median, marked provisional)."))
        info.setWordWrap(True)
        info.setObjectName("hint")
        lay.addWidget(info)

        g1 = QGroupBox(tr("关键因子筛选结果（阶段A 自动产出）", "Key-factor screening (auto from Stage A)"))
        v1 = QVBoxLayout(g1)
        self.screen_table = QTableWidget(0, 8)
        self.screen_table.setHorizontalHeaderLabels(
            [tr("因子", "Factor"), tr("MI(补充参考)", "MI (ref.)"), "Spearman ρ", tr("p 值", "p-value"),
             tr("bootstrap 入选率", "bootstrap freq"), tr("相关方向", "Direction"),
             tr("MI&ρ阈值(参考)", "MI&ρ rule (ref.)"), tr("用于动态标准", "Used in standard")])
        self.screen_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        v1.addWidget(self.screen_table)
        lay.addWidget(g1, 1)

        g2 = QGroupBox(tr("阈值标定", "Threshold calibration"))
        f2 = QGridLayout(g2)
        f2.addWidget(QLabel(tr("标定模式", "Mode")), 0, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([tr("SWAT 分位数（provisional）", "SWAT quantile (provisional)"),
                                  tr("监测数据 ROC/Youden", "Monitoring ROC/Youden"),
                                  tr("手动", "Manual")])
        f2.addWidget(self.mode_combo, 0, 1)
        f2.addWidget(QLabel(tr("分位数 q", "Quantile q")), 0, 2)
        self.q_spin = QDoubleSpinBox()
        self.q_spin.setRange(0.05, 0.95)
        self.q_spin.setSingleStep(0.05)
        self.q_spin.setValue(0.5)
        f2.addWidget(self.q_spin, 0, 3)

        self.mon_edit = QLineEdit()
        self.mon_edit.setPlaceholderText(tr("监测数据 CSV（列：Month, TN, Algae）",
                                            "Monitoring CSV (cols: Month, TN, Algae)"))
        btn_mon = QPushButton(tr("选择监测CSV…", "Pick monitoring CSV…"))
        btn_mon.clicked.connect(self._browse_mon)
        f2.addWidget(QLabel(tr("监测数据", "Monitoring")), 1, 0)
        f2.addWidget(self.mon_edit, 1, 1, 1, 2)
        f2.addWidget(btn_mon, 1, 3)

        self.factor_table = QTableWidget(0, 4)
        self.factor_table.setHorizontalHeaderLabels(
            [tr("因子", "Factor"), tr("方向", "Direction"), tr("阈值", "Threshold"), tr("来源", "Provenance")])
        self.factor_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        f2.addWidget(self.factor_table, 2, 0, 1, 4)

        f2.addWidget(QLabel(tr("应用范围", "Apply to")), 3, 0)
        self.scope_combo = QComboBox()
        self.scope_combo.addItems([tr("所有年份（全局标准）", "All years (global standard)"),
                                   tr("仅当前年份", "Current year only")])
        f2.addWidget(self.scope_combo, 3, 1)

        btn_calib = QPushButton(tr("执行标定并刷新动态标准", "Calibrate and refresh dynamic standard"))
        btn_calib.clicked.connect(self._do_calibrate)
        btn_val = QPushButton(tr("用监测数据做有效性验证 (AUC)", "Validate with monitoring (AUC)"))
        btn_val.clicked.connect(self._do_validate)
        f2.addWidget(btn_calib, 4, 1)
        f2.addWidget(btn_val, 4, 3)
        self.auc_label = QLabel("AUC: —")
        self.auc_label.setStyleSheet("font-weight:600;")
        f2.addWidget(self.auc_label, 5, 0, 1, 4)
        lay.addWidget(g2)

    def _browse_mon(self):
        p, _ = QFileDialog.getOpenFileName(self, tr("选择监测数据 CSV", "Pick monitoring CSV"), "", "CSV (*.csv)")
        if p:
            self.mon_edit.setText(p)

    def _fill_screening(self):
        sc = getattr(self.state.sa, "screening", None)
        self.screen_table.setRowCount(0)
        proj = self.state.project
        used = set()
        if proj:
            used = {f.name for f in proj.calibration_for_year(self.state.current_year).factors}
        if sc is not None and not sc.empty:
            for _, r in sc.iterrows():
                i = self.screen_table.rowCount()
                self.screen_table.insertRow(i)
                in_std = r["feature"] in used
                direction = str(r.get("Direction", ""))
                dir_txt = tr("正相关", "positive") if direction == "positive" else tr("负相关", "negative")
                # MI&ρ 参考规则；对仅 MI 卡住(|ρ|达标但 MI 偏低)的因子注明原因，避免误解
                mi_v = float(r.get("MI_Score", 0) or 0)
                rho_v = abs(float(r.get("Spearman_Corr", 0) or 0))
                if r.get("Selected"):
                    pass_txt = tr("达标", "passed")
                elif rho_v > 0.3 and mi_v <= 0.05:
                    pass_txt = tr("未达标(仅MI偏低)", "not passed (MI low only)")
                else:
                    pass_txt = tr("未达标", "not passed")
                used_txt = tr("是", "yes") if in_std else tr("否", "no")
                vals = [r["feature"], f"{r['MI_Score']:.3f}", f"{r['Spearman_Corr']:.3f}",
                        f"{r['Spearman_p']:.3f}", f"{r['Boot_Selected_Freq']:.2f}",
                        dir_txt, pass_txt, used_txt]
                for j, v in enumerate(vals):
                    self.screen_table.setItem(i, j, QTableWidgetItem(str(v)))
        self._fill_factors()

    def _fill_factors(self):
        proj = self.state.project
        self.factor_table.setRowCount(0)
        if not proj:
            return
        for f in proj.calibration_for_year(self.state.current_year).factors:
            i = self.factor_table.rowCount()
            self.factor_table.insertRow(i)
            self.factor_table.setItem(i, 0, QTableWidgetItem(f.name))
            self.factor_table.setItem(i, 1, QTableWidgetItem(f.direction))
            self.factor_table.setItem(i, 2, QTableWidgetItem("" if f.threshold is None else f"{f.threshold:.3f}"))
            self.factor_table.setItem(i, 3, QTableWidgetItem(f.provenance))

    def _collect_manual(self):
        out = {}
        for i in range(self.factor_table.rowCount()):
            name = self.factor_table.item(i, 0).text()
            tv = self.factor_table.item(i, 2).text().strip()
            if tv:
                try:
                    out[name] = float(tv)
                except ValueError:
                    pass
        return out

    def _do_calibrate(self):
        from ..calibration import calibrate_thresholds
        proj = self.state.project
        if not proj or self.state.sa is None:
            QMessageBox.warning(self, tr("提示", "Notice"),
                                tr("请先在「运行」页完成阶段A。", "Run Stage A first (Run tab)."))
            return
        method = ["swat_quantile", "monitoring_roc", "manual"][self.mode_combo.currentIndex()]
        # 基于当前生效标定的因子做重标定
        base_calib = proj.calibration_for_year(self.state.current_year)
        calib = calibrate_thresholds(base_calib.factors, self.state.sa.subattr,
                                     method=method, quantile=self.q_spin.value(),
                                     manual=self._collect_manual())
        if self.scope_combo.currentIndex() == 1 and self.state.current_year is not None:
            # 仅当前年份：存为逐年标定，不影响其他年份
            proj.calibration_by_year[self.state.current_year] = calib
            scope_msg = tr(f"仅 {self.state.current_year} 年", f"year {self.state.current_year} only")
        else:
            proj.calibration = calib
            scope_msg = tr("所有年份", "all years")
        # run_stage_b 会用 calibration_for_year 重算 动态标准→Wi→容量→风险
        self.state.recompute_stage_b()
        self._fill_factors()
        self.status_cb(tr(f"标定完成（{method}，{scope_msg}）。动态标准/容量/风险已同步更新。",
                          f"Calibrated ({method}, {scope_msg}). Standard/capacity/risk updated.") +
                       (tr("【provisional】", " [provisional]") if calib.is_provisional else ""))

    def _do_validate(self):
        from ..calibration import validate_standard
        path = self.mon_edit.text().strip()
        if not path or not os.path.isfile(path):
            QMessageBox.warning(self, tr("提示", "Notice"),
                                tr("请先选择监测数据 CSV（列：Month, TN, Algae）。",
                                   "Pick a monitoring CSV (cols: Month, TN, Algae)."))
            return
        try:
            res = validate_standard(pd.read_csv(path))
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, tr("验证失败", "Validation failed"), str(e))
            return
        auc = res.get("auc_dynamic", float("nan"))
        txt = tr(f"动态体系 AUC = {auc:.3f}　|　静态对照: ", f"Dynamic AUC = {auc:.3f}  |  static: ")
        txt += "  ".join(f"{k}→AUC{v['auc']:.2f}" for k, v in res.get("static", {}).items())
        self.auc_label.setText(txt)
        if self.state.project:
            self.state.project.calibration.auc = {"dynamic": auc}


# ============================================================================
# ③ 运行
# ============================================================================
class RunPanel(QWidget):
    def __init__(self, state, status_cb=None):
        super().__init__()
        self.state = state
        self.status_cb = status_cb or (lambda *_: None)
        self._build()
        state.stageAProgress.connect(self._on_progress)
        state.stageAReady.connect(lambda: self._set_busy(False, tr("阶段A 完成。", "Stage A done.")))
        state.stageAFailed.connect(self._on_failed)
        state.logMessage.connect(self._log)
        state.projectChanged.connect(self._populate_years)

    def _build(self):
        lay = QVBoxLayout(self)

        gy = QGroupBox(tr("模拟期与预热设置", "Simulation period & spin-up"))
        vy = QVBoxLayout(gy)
        self.cio_label = QLabel("")
        self.cio_label.setWordWrap(True)
        self.cio_label.setObjectName("hint")
        vy.addWidget(self.cio_label)
        rowy = QHBoxLayout()
        rowy.addWidget(QLabel(tr("预热年数 NYSKIP（前 N 年作为预热，必为早期连续段）",
                                 "Spin-up years NYSKIP (first N years, always an early contiguous block)")))
        self.nyskip_spin = QSpinBox()
        self.nyskip_spin.setRange(0, 50)
        self.nyskip_spin.valueChanged.connect(self._update_sel_label)
        rowy.addWidget(self.nyskip_spin)
        rowy.addStretch(1)
        vy.addLayout(rowy)
        self.sel_label = QLabel("")
        self.sel_label.setWordWrap(True)
        vy.addWidget(self.sel_label)
        lay.addWidget(gy)

        g = QGroupBox(tr("仿真与分析流程", "Simulation and analysis pipeline"))
        v = QVBoxLayout(g)
        row = QHBoxLayout()
        self.btn_swat = QPushButton(tr("① 运行 SWAT 仿真", "① Run SWAT simulation"))
        self.btn_swat.clicked.connect(self._run_swat)
        self.btn_stage_a = QPushButton(tr("② 运行分析链路（阶段A）", "② Run analysis pipeline (Stage A)"))
        self.btn_stage_a.clicked.connect(self._run_stage_a)
        row.addWidget(self.btn_swat)
        row.addWidget(self.btn_stage_a)
        v.addLayout(row)
        self.bar = QProgressBar()
        v.addWidget(self.bar)
        lay.addWidget(g)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        lay.addWidget(self.log, 1)
        self._populate_years()

    def _populate_years(self):
        from ..swat_io import read_file_cio
        proj = self.state.project
        self._iyr = self._nbyr = None
        self.nyskip_spin.blockSignals(True)
        if not proj:
            self.cio_label.setText("")
            self.nyskip_spin.blockSignals(False)
            return
        cio = read_file_cio(proj.txtinout)
        iyr, nbyr, nyskip = cio.get("iyr"), cio.get("nbyr"), cio.get("nyskip") or 0
        self._iyr, self._nbyr = iyr, nbyr
        out_years = proj.years or cio.get("output_years", [])
        if iyr and nbyr:
            self.nyskip_spin.setRange(0, max(0, nbyr - 1))
            self.nyskip_spin.setValue(nyskip)
            self.cio_label.setText(tr(
                f"SWAT 模拟期：{iyr}–{iyr + nbyr - 1}（共 {nbyr} 年，IYR={iyr}）。\n"
                f"预热(NYSKIP)由你设定（当前 file.cio 为 {nyskip} 年）——可在下方修改；"
                f"运行 SWAT 时会写入 file.cio，预热即“前 NYSKIP 年”，故必为早期连续段。\n"
                f"当前可分析的输出年份：{out_years[0]}–{out_years[-1]}（共 {len(out_years)} 年）。"
                f"若把 NYSKIP 调小到已有输出之前，需重跑 SWAT 才能得到更早年份。",
                f"SWAT period: {iyr}–{iyr + nbyr - 1} ({nbyr} yr, IYR={iyr}).\n"
                f"Spin-up (NYSKIP) is YOUR choice (file.cio currently = {nyskip} yr) — edit below; "
                f"it is written to file.cio when you Run SWAT, so spin-up is always the 'first NYSKIP years' "
                f"(an early contiguous block).\nOutput years currently available: "
                f"{out_years[0]}–{out_years[-1]} ({len(out_years)} yr). Lowering NYSKIP below the existing "
                f"output requires re-running SWAT to obtain earlier years."))
        self.nyskip_spin.blockSignals(False)
        self._update_sel_label()

    def _selected_years(self):
        """用于多年平均的年份 = 输出年份中 ≥ (IYR + NYSKIP) 的部分（预热=早期连续段）。"""
        proj = self.state.project
        out_years = (proj.years if proj else []) or []
        if self._iyr is None:
            return list(out_years)
        cutoff = self._iyr + self.nyskip_spin.value()
        sel = [y for y in out_years if y >= cutoff]
        return sel or list(out_years)

    def _update_sel_label(self):
        ys = self._selected_years()
        if ys and self._iyr is not None:
            warm_end = self._iyr + self.nyskip_spin.value() - 1
            warm = f"{self._iyr}–{warm_end}" if self.nyskip_spin.value() > 0 else tr("无", "none")
            self.sel_label.setText(tr(
                f"→ 预热年份：{warm}　|　用于多年平均的年份：{ys[0]}–{ys[-1]}（共 {len(ys)} 年）",
                f"→ spin-up: {warm}  |  years used for multi-year average: {ys[0]}–{ys[-1]} ({len(ys)} yr)"))
        else:
            self.sel_label.setText("")

    def _run_swat(self):
        proj = self.state.project
        if not proj:
            QMessageBox.warning(self, tr("提示", "Notice"), tr("请先载入工程。", "Load a project first."))
            return
        if not proj.swat_exe:
            QMessageBox.warning(self, tr("提示", "Notice"),
                                tr("未找到 SWAT 可执行文件，可直接运行阶段A分析既有输出。",
                                   "No SWAT exe found; you can run Stage A on existing output."))
            return
        from .state import SwatWorker
        from ..swat_io import write_file_cio_nyskip
        # 将用户设定的预热年数写入 file.cio，使本次仿真按该预热运行
        ns = self.nyskip_spin.value()
        if write_file_cio_nyskip(proj.txtinout, ns):
            self._log(tr(f"已将预热年数 NYSKIP={ns} 写入 file.cio。",
                         f"Wrote spin-up NYSKIP={ns} to file.cio."))
        self._set_busy(True, tr("SWAT 仿真中…", "Running SWAT…"))
        self._swat_worker = SwatWorker(proj.swat_exe, proj.txtinout)
        self._swat_worker.log.connect(self._log)
        self._swat_worker.done.connect(self._on_swat_done)
        self._swat_worker.start()

    def _on_swat_done(self, code):
        self._log(tr(f"\nSWAT 结束，返回码 {code}。", f"\nSWAT finished, code {code}."))
        if code == 0:
            # 重跑后输出年份可能改变，刷新工程年份
            from ..swat_io import read_file_cio
            proj = self.state.project
            if proj:
                cio = read_file_cio(proj.txtinout)
                if cio.get("output_years"):
                    proj.years = cio["output_years"]
                    self._populate_years()
            self._log(tr("自动进入阶段A …", "Entering Stage A …"))
            self._run_stage_a()
        else:
            self._set_busy(False, tr("SWAT 失败。", "SWAT failed."))

    def _run_stage_a(self):
        if not self.state.project:
            return
        sel = self._selected_years()
        if not sel:
            QMessageBox.warning(self, tr("提示", "Notice"),
                                tr("请至少勾选一个模拟年份。", "Select at least one simulation year."))
            return
        self.state.project.analysis_years = sel
        self._log(tr(f"采用模拟年份做多年平均: {sel}", f"Multi-year average over: {sel}"))
        self._set_busy(True, tr("阶段A 计算中…", "Computing Stage A…"))
        self.state.start_stage_a()

    def _on_progress(self, msg, frac):
        self.bar.setValue(int(frac * 100))
        self._log(f"[{frac*100:5.1f}%] {msg}")

    def _on_failed(self, err):
        self._set_busy(False, tr("阶段A 失败。", "Stage A failed."))
        QMessageBox.critical(self, tr("阶段A 失败", "Stage A failed"), err[:1500])

    def _set_busy(self, busy, msg=""):
        self.btn_swat.setEnabled(not busy)
        self.btn_stage_a.setEnabled(not busy)
        if msg:
            self.status_cb(msg)

    def _log(self, text):
        self.log.appendPlainText(text)


# ============================================================================
# ④ 点源 + 交互地图 + 详情（核心）
# ============================================================================
class DetailPanel(QWidget):
    def __init__(self, state=None):
        super().__init__()
        self.state = state
        lay = QVBoxLayout(self)
        self.title = QLabel(tr("子流域详情", "Subbasin details"))
        self.title.setObjectName("detailTitle")
        lay.addWidget(self.title)
        self.body = QTextEdit()
        self.body.setReadOnly(True)
        lay.addWidget(self.body, 1)
        self.chart = DetailMiniChart()
        lay.addWidget(self.chart)
        self.show_row(None)

    def _name(self, sub):
        if self.state and self.state.project:
            return self.state.project.subbasin_name(sub, i18n.get_lang())
        return ""

    def show_row(self, row):
        if row is None:
            self.title.setText(tr("子流域详情", "Subbasin details"))
            self.body.setHtml("<p style='color:#888;font-size:16px'>" +
                              tr("点击地图中的任一子流域以查看其动态自适应标准、环境容量与两类风险等级。",
                                 "Click any subbasin on the map to see its dynamic standard, capacity and two risk classes.") +
                              "</p>")
            self.chart.show_subbasin(None)
            return
        sub = int(row["SUB"])
        rc_lp = int(row.get("RiskClass_LP", 0) or 0)
        rc_tr = int(row.get("RiskClass_TR", 0) or 0)
        name = self._name(sub)
        head = tr(f"子流域 {sub}", f"Subbasin {sub}") + (f"　{name}" if name else "")
        self.title.setText(head)

        def badge(c):
            return (f"<span style='background:{RISK_CLASS_COLORS.get(c,'#ccc')};color:#fff;"
                    f"padding:1px 9px;border-radius:9px;'>{i18n.risk_label(c)}</span>")

        L = tr  # alias
        gb = i18n.gb_label(row.get("GB_class"))
        rec = i18n.gb_label(row.get("Recommended_Class"))
        has_actual = pd.notna(row.get("W_actual_kg_d"))

        rows = [
            (L('GB 类别', 'GB class'), gb),
            (L('原始(严)标准', 'Strict standard'), f"{_f(row.get('C_strict'))} mg/L"),
            (f"<b>{L('动态自适应标准', 'Dynamic standard')}</b>",
             f"<b>{_f(row.get('C_dynamic'))} mg/L</b>（{rec}）"),
            (L('调整指数', 'Adjustment index'), _f(row.get('Adjustment_Index'))),
            ("<hr>", ""),
            (L('基础环境容量 Wi', 'Base capacity Wi'), f"{_f(row.get('Wi_kg_d'),1)} kg/d"),
        ]
        if has_actual:
            hot = tr("⚠ 是", "⚠ Yes") if bool(row.get("IsTransmissionHotspot")) else tr("否", "No")
            rows += [
                (L('点源负荷', 'Point load'), f"{_f(row.get('point_load_kgd'),2)} kg/d"),
                (f"<b>{L('实际环境容量', 'Actual capacity')}</b>",
                 f"<b>{_f(row.get('W_actual_kg_d'),1)} kg/d</b>"),
                ("<hr>", ""),
                (L('第一类风险·本地 LP', 'Risk-1 Local LP'), f"{_f(row.get('LP'))}　{badge(rc_lp)}"),
                (L('第二类风险·上游 TR', 'Risk-2 Upstream TR'), f"{_f(row.get('TR'))}　{badge(rc_tr)}"),
                (L('上游来量 Influx', 'Upstream inflow'), f"{_f(row.get('Influx_kgd'),1)} kg/d"),
                (L('外来贡献比', 'Import fraction'), _f(row.get('Import_Fraction'))),
                (L('节点类型', 'Node type'), i18n.node_label(row.get('Node_Type', '—'))),
                (L('传输热点', 'Transmission hotspot'), f"<b>{hot}</b>"),
            ]
        body_rows = "".join(
            (f"<tr><td colspan=2><hr></td></tr>" if k == "<hr>"
             else f"<tr><td>{k}</td><td>{v}</td></tr>")
            for k, v in rows)
        note = "" if has_actual else (
            f"<p style='color:#b7791f;font-size:14px;'>" +
            tr("该年份无点源污染数据，未计算实际环境容量与风险（仅显示动态标准与基础容量）。",
               "No point-source data for this year — actual capacity and risk are not computed "
               "(showing dynamic standard and base capacity only).") + "</p>")
        self.body.setHtml(f"<table cellpadding=5 style='font-size:16px;'>{body_rows}</table>{note}")
        self.chart.show_subbasin(row if has_actual else None)


class MapInteractPanel(QWidget):
    def __init__(self, state, status_cb=None):
        super().__init__()
        self.state = state
        self.status_cb = status_cb or (lambda *_: None)
        self._tmp_html = os.path.join(tempfile.gettempdir(), "wec_map.html")
        self._build()
        self.reconnect()

    def reconnect(self):
        """(重新)连接 state 信号。语言切换时本面板保留实例，故需重连。"""
        self.state.projectChanged.connect(self._rebuild_pointsource_table)
        self.state.stageAReady.connect(self._on_stage_ready)
        self.state.resultsChanged.connect(self.refresh_map)

    def _build(self):
        from PyQt5.QtWebEngineWidgets import QWebEngineView
        from PyQt5.QtWebChannel import QWebChannel
        from .bridge import MapBridge

        splitter = QSplitter(Qt.Horizontal)
        QVBoxLayout(self).addWidget(splitter)

        # 左：点源编辑
        left = QWidget()
        lv = QVBoxLayout(left)
        self.ps_title = QLabel(tr("<b>点源污染输入 (g/s)</b>", "<b>Point-source input (g/s)</b>"))
        lv.addWidget(self.ps_title)
        self.ps_table = QTableWidget(0, 2)
        self.ps_table.setHorizontalHeaderLabels([tr("子流域", "Sub"), tr("点源 (g/s)", "Point (g/s)")])
        self.ps_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        lv.addWidget(self.ps_table, 1)
        self._ps_btns = []
        for zh, en, slot in [("从 CSV 载入点源", "Load point source CSV", self._load_ps_csv),
                             ("应用并重算（实时刷新）", "Apply and recompute (live)", self._apply_ps),
                             ("重置为该年默认", "Reset to year default", self._reset_ps)]:
            b = QPushButton(tr(zh, en))
            b.clicked.connect(slot)
            lv.addWidget(b)
            self._ps_btns.append((b, zh, en))
        splitter.addWidget(left)

        # 中：地图
        center = QWidget()
        cv = QVBoxLayout(center)
        ctrl = QHBoxLayout()
        self.lbl_layer = QLabel(tr("专题图层", "Layer"))
        ctrl.addWidget(self.lbl_layer)
        self.layer_combo = QComboBox()
        for k in LAYER_DEFS:
            self.layer_combo.addItem(layer_label(k), k)
        self.layer_combo.setCurrentIndex(len(LAYER_DEFS) - 1)
        self.layer_combo.currentIndexChanged.connect(self.refresh_map)
        ctrl.addWidget(self.layer_combo)
        self.lbl_year = QLabel(tr("年份", "Year"))
        ctrl.addWidget(self.lbl_year)
        self.year_combo = QComboBox()
        self.year_combo.currentIndexChanged.connect(self._on_year)
        ctrl.addWidget(self.year_combo)
        self.btn_export = QPushButton(tr("导出当前结果 CSV", "Export current CSV"))
        self.btn_export.clicked.connect(self._export)
        ctrl.addWidget(self.btn_export)
        ctrl.addStretch(1)
        cv.addLayout(ctrl)

        self.view = QWebEngineView()
        self.bridge = MapBridge()
        self.channel = QWebChannel()
        self.channel.registerObject("pyBridge", self.bridge)
        self.view.page().setWebChannel(self.channel)
        self.bridge.clicked.connect(self._on_subbasin_clicked)
        cv.addWidget(self.view, 1)
        splitter.addWidget(center)

        # 右：详情
        self.detail = DetailPanel(self.state)
        splitter.addWidget(self.detail)
        splitter.setSizes([280, 800, 380])

    def retranslate(self):
        """语言切换时就地更新本面板文本并重绘地图（不重建 QWebEngineView，避免崩溃）。"""
        self.ps_title.setText(tr("<b>点源污染输入 (g/s)</b>", "<b>Point-source input (g/s)</b>"))
        self.ps_table.setHorizontalHeaderLabels([tr("子流域", "Sub"), tr("点源 (g/s)", "Point (g/s)")])
        for b, zh, en in self._ps_btns:
            b.setText(tr(zh, en))
        self.lbl_layer.setText(tr("专题图层", "Layer"))
        self.lbl_year.setText(tr("年份", "Year"))
        self.btn_export.setText(tr("导出当前结果 CSV", "Export current CSV"))
        cur = self.layer_combo.currentData()
        self.layer_combo.blockSignals(True)
        self.layer_combo.clear()
        for k in LAYER_DEFS:
            self.layer_combo.addItem(layer_label(k), k)
        i = list(LAYER_DEFS).index(cur) if cur in LAYER_DEFS else len(LAYER_DEFS) - 1
        self.layer_combo.setCurrentIndex(i)
        self.layer_combo.blockSignals(False)
        self.detail.show_row(None)
        self.refresh_map()

    def _rebuild_pointsource_table(self):
        proj = self.state.project
        self.ps_table.setRowCount(0)
        if not proj:
            return
        self.ps_table.setRowCount(proj.n_subbasins)
        for i in range(proj.n_subbasins):
            it0 = QTableWidgetItem(str(i + 1))
            it0.setFlags(it0.flags() & ~Qt.ItemIsEditable)
            self.ps_table.setItem(i, 0, it0)
            self.ps_table.setItem(i, 1, QTableWidgetItem("0"))
        # 年份下拉：列出「全部」输出年份。有专属点源的年份做完整容量+风险；其余仅显示动态标准+基础容量。
        ps = set(proj.point_source_years)
        years = proj.years or []
        self.year_combo.blockSignals(True)
        self.year_combo.clear()
        for y in years:
            tag = tr(" ✓含点源", " ✓point src") if y in ps else tr(" ·仅标准/容量", " ·std/cap only")
            self.year_combo.addItem(f"{y}{tag}", y)
        # 默认选含点源的最新年份（若有），否则最后一年
        default_year = (proj.point_source_years or years)[-1] if years else None
        if default_year in years:
            self.year_combo.setCurrentIndex(years.index(default_year))
        self.year_combo.blockSignals(False)
        self._fill_ps_for_year()

    def _on_stage_ready(self):
        self._fill_ps_for_year()
        self.refresh_map()

    def _fill_ps_for_year(self):
        """按当前年份的专属点源文件填表（显示用；无文件则全 0）。"""
        proj = self.state.project
        if not proj:
            return
        df = pipeline.load_point_source(proj, self.state.current_year, strict=True)
        m = dict(zip(df["SUB"], df["point_kgd"]))
        for i in range(self.ps_table.rowCount()):
            sub = int(self.ps_table.item(i, 0).text())
            self.ps_table.setItem(i, 1, QTableWidgetItem(f"{m.get(sub, 0.0) / 86.4:.6g}"))

    def _table_to_point_df(self):
        rows = []
        for i in range(self.ps_table.rowCount()):
            sub = int(self.ps_table.item(i, 0).text())
            try:
                gs = float(self.ps_table.item(i, 1).text())
            except (ValueError, AttributeError):
                gs = 0.0
            rows.append({"SUB": sub, "point_kgd": gs * 86.4})
        return pd.DataFrame(rows)

    def _apply_ps(self):
        if self.state.sa is None:
            QMessageBox.warning(self, tr("提示", "Notice"), tr("请先完成阶段A。", "Complete Stage A first."))
            return
        self.state.recompute_stage_b(point_df=self._table_to_point_df())
        self.status_cb(tr("点源已应用，结果与地图已刷新。", "Point source applied; results & map refreshed."))

    def _load_ps_csv(self):
        p, _ = QFileDialog.getOpenFileName(self, tr("选择点源 CSV", "Pick point-source CSV"), "", "CSV (*.csv)")
        if not p or not self.state.project:
            return
        try:
            pol = self.state.project.pollutant
            df = pd.read_csv(p).rename(columns={pol.point_subbasin_col: "SUB"})
            vcol = pol.point_value_col if pol.point_value_col in df.columns else df.columns[-1]
            m = dict(zip(df["SUB"].astype(int), pd.to_numeric(df[vcol], errors="coerce").fillna(0)))
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, tr("载入失败", "Load failed"), str(e))
            return
        for i in range(self.ps_table.rowCount()):
            sub = int(self.ps_table.item(i, 0).text())
            self.ps_table.setItem(i, 1, QTableWidgetItem(f"{m.get(sub, 0.0):.6g}"))
        self._apply_ps()

    def _reset_ps(self):
        if not self.state.project:
            return
        self.state.point_df = None        # 清除手动覆盖，回到该年专属点源
        self._fill_ps_for_year()
        if self.state.sa is not None:
            self.state.recompute_stage_b()

    def _on_year(self):
        y = self.year_combo.currentData()
        if y is None:
            return
        y = int(y)
        has_ps = self.state.project and self.state.project.has_point_source(y)
        # 无点源年份：若当前在依赖点源的图层，自动切到「动态标准」，避免整屏灰
        if not has_ps and self.layer_combo.currentData() in ("W_actual_kg_d", "RiskClass_LP", "RiskClass_TR"):
            self.layer_combo.blockSignals(True)
            self.layer_combo.setCurrentIndex(0)   # C_dynamic
            self.layer_combo.blockSignals(False)
        if self.state.sa is not None:
            self.state.set_year(y)
        else:
            self.state.current_year = y
        self._fill_ps_for_year()
        if not has_ps:
            self.status_cb(tr(f"{y} 年无点源数据：仅显示动态标准与基础容量（如已获取点源，可在左侧录入后“应用并重算”）。",
                              f"Year {y} has no point source: showing dynamic standard & base capacity only "
                              f"(enter point source on the left and click Apply to compute)."))

    def refresh_map(self):
        if self.state.gdf_merged is None or self.state.sa is None:
            return
        key = self.layer_combo.currentData()
        try:
            build_map_html(self.state.project, self.state.gdf_merged, self.state.rivers,
                           self.state.sa.topology, key, self._tmp_html, year=self.state.current_year)
            self.view.load(QUrl.fromLocalFile(os.path.abspath(self._tmp_html)))
        except Exception as e:  # noqa: BLE001
            self.status_cb(tr(f"地图生成失败: {e}", f"Map build failed: {e}"))

    def _on_subbasin_clicked(self, sub_id):
        self.detail.show_row(self.state.subbasin_row(sub_id))
        self.status_cb(tr(f"已选中子流域 {sub_id}", f"Selected subbasin {sub_id}"))

    def _export(self):
        if self.state.result_df is None:
            QMessageBox.warning(self, tr("提示", "Notice"), tr("尚无结果。", "No results yet."))
            return
        p, _ = QFileDialog.getSaveFileName(self, tr("导出结果", "Export results"), "result.csv", "CSV (*.csv)")
        if p:
            self.state.result_df.to_csv(p, index=False, encoding="utf-8-sig")
            self.status_cb(tr(f"已导出：{p}", f"Exported: {p}"))


def _f(v, nd=3):
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "—"
        return f"{float(v):.{nd}f}"
    except (TypeError, ValueError):
        return str(v)
