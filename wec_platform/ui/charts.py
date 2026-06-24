"""
charts.py — matplotlib 嵌入式图表 / embedded charts
=====================================================
MplCanvas、DetailMiniChart（单子流域容量平衡）、ChartsPanel（概览）。双语 + 放大字号。
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavToolbar
import matplotlib.pyplot as plt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QComboBox, QHBoxLayout, QLabel,
                             QSizePolicy)

from ..config import RISK_CLASS_COLORS
from .. import i18n
from ..i18n import tr

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["font.size"] = 13


class MplCanvas(FigureCanvas):
    def __init__(self, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi, tight_layout=True)
        super().__init__(self.fig)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(10, 10)
        self.updateGeometry()

    def clear(self):
        self.fig.clear()


class DetailMiniChart(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.canvas = MplCanvas(width=3.2, height=2.3, dpi=98)
        lay.addWidget(self.canvas)

    def show_subbasin(self, row):
        self.canvas.clear()
        ax = self.canvas.fig.add_subplot(111)
        if row is None:
            ax.text(0.5, 0.5, tr("点击地图中的子流域", "Click a subbasin on the map"),
                    ha="center", va="center", fontsize=10)
            ax.axis("off")
            self.canvas.draw()
            return
        wi = float(row.get("Wi_kg_d", 0) or 0)
        pt = float(row.get("point_load_kgd", 0) or 0)
        wa = float(row.get("W_actual_kg_d", 0) or 0)
        labels = [tr("基础容量", "Base"), tr("点源负荷", "Point src"), tr("实际容量", "Actual")]
        vals = [wi, pt, wa]
        colors = ["#4575b4", "#fdae61", "#1a9850" if wa >= 0 else "#a50026"]
        bars = ax.bar(labels, vals, color=colors)
        ax.axhline(0, color="#555", lw=0.8)
        ax.set_ylabel("kg/d", fontsize=10)
        ax.set_title(tr(f"子流域 {int(row['SUB'])} 容量平衡",
                        f"Subbasin {int(row['SUB'])} capacity balance"), fontsize=11)
        ax.tick_params(labelsize=9)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.0f}",
                    ha="center", va="bottom" if v >= 0 else "top", fontsize=9)
        self.canvas.draw()


class ChartsPanel(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)
        top = QHBoxLayout()
        top.addWidget(QLabel(tr("图表：", "Chart:")))
        self.combo = QComboBox()
        self._items = [
            tr("实际环境容量（按子流域）", "Actual capacity (by subbasin)"),
            tr("两类风险等级分布", "Two-risk class distribution"),
            tr("动态标准 vs 原始标准", "Dynamic vs strict standard"),
            tr("关键因子重要性 (MI)", "Key-factor importance (MI)"),
        ]
        self.combo.addItems(self._items)
        self.combo.currentIndexChanged.connect(self.refresh)
        top.addWidget(self.combo)
        top.addSpacing(16)
        self.year_label = QLabel("")
        self.year_label.setStyleSheet("font-size:16px; font-weight:700; color:#2b6cb0;")
        top.addWidget(self.year_label)
        top.addStretch(1)
        lay.addLayout(top)
        self.canvas = MplCanvas(width=7, height=5, dpi=100)
        self.toolbar = NavToolbar(self.canvas, self)
        lay.addWidget(self.toolbar, 0)
        lay.addWidget(self.canvas, 1)          # 占满剩余全部纵向空间
        state.resultsChanged.connect(self.refresh)

    def _context(self):
        """当前数据的年份与污染物文字（用于标注图表）。"""
        yr = getattr(self.state, "current_year", None)
        pol = self.state.project.pollutant if self.state.project else None
        pol_txt = (pol.name_cn if (pol and not i18n.is_en()) else (pol.code if pol else ""))
        yr_txt = (f"{yr}" + tr("年", "")) if yr else tr("（多年平均）", "(multi-year)")
        return yr_txt, pol_txt

    def refresh(self):
        df = self.state.result_df
        self.canvas.clear()
        yr_txt, pol_txt = self._context()
        idx = self.combo.currentIndex()
        # 第④项(关键因子重要性)与年份无关，其余均为该年数据
        year_dependent = idx != 3
        self.year_label.setText(
            tr(f"数据年份：{yr_txt}　|　污染物：{pol_txt}" if year_dependent
               else f"污染物：{pol_txt}（与年份无关）",
               f"Data year: {yr_txt}  |  Pollutant: {pol_txt}" if year_dependent
               else f"Pollutant: {pol_txt} (year-independent)"))
        ax = self.canvas.fig.add_subplot(111)
        if df is None or df.empty:
            ax.text(0.5, 0.5, tr("尚无结果，请先运行阶段A", "No results yet — run Stage A first"),
                    ha="center", va="center", fontsize=12)
            ax.axis("off")
            self.canvas.draw()
            return
        try:
            [self._cap, self._risk, self._std, self._feat][idx](ax, df)
        except Exception as e:  # noqa: BLE001
            ax.clear()
            ax.text(0.5, 0.5, f"{tr('绘图错误','Plot error')}: {e}", ha="center", va="center", wrap=True)
            ax.axis("off")
            self.canvas.draw()
            return
        # 把年份/污染物折进坐标轴标题首行（在图内可见、导出图也带年份，且不与标题重叠）
        ctx = (tr(f"{pol_txt}　{yr_txt}", f"{pol_txt}  {yr_txt}") if year_dependent
               else tr(f"{pol_txt}（与年份无关）", f"{pol_txt} (year-independent)"))
        base_title = ax.get_title()
        ax.set_title(f"{ctx}\n{base_title}" if base_title else ctx, fontsize=11)
        self.canvas.draw()

    def _cap(self, ax, df):
        d = df.sort_values("W_actual_kg_d")
        colors = ["#a50026" if v < 0 else "#1a9850" for v in d["W_actual_kg_d"]]
        ax.barh([str(int(s)) for s in d["SUB"]], d["W_actual_kg_d"], color=colors)
        ax.axvline(0, color="#333", lw=0.8)
        ax.set_xlabel(tr("实际水环境容量 (kg/d)", "Actual capacity (kg/d)"))
        ax.set_ylabel(tr("子流域", "Subbasin"))
        ax.set_title(tr("各子流域实际水环境容量（红=赤字/超载）",
                        "Actual capacity by subbasin (red = deficit)"))
        ax.tick_params(labelsize=8)

    def _risk(self, ax, df):
        import numpy as np
        classes = [1, 2, 3, 4, 5]
        lp = [int((df["RiskClass_LP"] == c).sum()) for c in classes]
        cu = [int((df["RiskClass_TR"] == c).sum()) for c in classes]
        x = np.arange(len(classes))
        w = 0.38
        ax.bar(x - w / 2, lp, w, label=tr("第一类·本地 LP", "Risk-1 Local LP"), color="#4575b4")
        ax.bar(x + w / 2, cu, w, label=tr("第二类·上游 TR", "Risk-2 Upstream TR"), color="#d73027")
        ax.set_xticks(x)
        ax.set_xticklabels([i18n.risk_label(c) for c in classes], rotation=18, fontsize=9)
        ax.set_ylabel(tr("子流域数量", "Subbasin count"))
        ax.set_title(tr("两类风险等级分布", "Two-risk class distribution"))
        ax.legend()

    def _std(self, ax, df):
        d = df.sort_values("SUB")
        x = [str(int(s)) for s in d["SUB"]]
        ax.plot(x, d["C_strict"], "o-", label=tr("原始(严)标准", "Strict std"), color="#2166ac")
        ax.plot(x, d["C_dynamic"], "s-", label=tr("动态自适应", "Dynamic"), color="#b2182b")
        ax.set_xlabel(tr("子流域", "Subbasin"))
        ax.set_ylabel(tr("标准 (mg/L)", "Standard (mg/L)"))
        ax.set_title(tr("动态自适应标准 vs 原始标准", "Dynamic vs strict standard"))
        ax.tick_params(axis="x", labelsize=8)
        ax.legend()

    def _feat(self, ax, df):
        sc = getattr(self.state.sa, "screening", None)
        if sc is None or sc.empty:
            ax.text(0.5, 0.5, tr("无因子筛选结果", "No screening result"), ha="center", va="center")
            ax.axis("off")
            return
        sc = sc.sort_values("MI_Score")
        colors = ["#1a9850" if s else "#bbbbbb" for s in sc.get("Selected", [False] * len(sc))]
        ax.barh(sc["feature"], sc["MI_Score"], color=colors)
        ax.set_xlabel(tr("互信息 MI（仅补充参考，n=32 下偏低且不稳）", "Mutual information (supplementary only; low/unstable at n=32)"))
        ax.set_title(tr("关键因子 MI（补充参考；绿=MI&ρ参考达标，非入选决定）",
                        "Key-factor MI (supplementary; green = MI&ρ rule, not the decision)"))
        ax.tick_params(labelsize=9)
