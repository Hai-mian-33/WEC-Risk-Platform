"""
main_window.py — 主窗口 / main window (bilingual)
==================================================
五个步骤页签共享一个 AppState。切换语言时重建页签与菜单并从当前状态重新填充。
"""
from __future__ import annotations

import os
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMainWindow, QTabWidget, QAction, QStatusBar, QMessageBox

from .state import AppState
from .panels import ProjectPanel, CalibPanel, RunPanel, MapInteractPanel
from .charts import ChartsPanel
from .. import i18n
from ..i18n import tr
from ..project import Project


def _example_root() -> str:
    """示例工程目录：随程序分发的 data/Miyun（与 git 仓库/exe 同级，相对解析，可迁移）。
    若该目录缺失，由 _load_example() 弹出"未找到示例目录"提示引导用户自行选择工程。"""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "data", "Miyun")


EXAMPLE_ROOT = _example_root()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(1560, 960)
        self.state = AppState()
        self.setStatusBar(QStatusBar())
        self.tabs = QTabWidget()
        self.tabs.setMovable(False)
        # 页签随文字长度自适应：不省略文字，超宽时用滚动按钮而非截断
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setElideMode(Qt.ElideNone)
        self.tabs.tabBar().setElideMode(Qt.ElideNone)
        self.tabs.tabBar().setExpanding(False)
        self.tabs.tabBar().setUsesScrollButtons(True)
        self.setCentralWidget(self.tabs)
        self._build_tabs()
        self._build_menu()
        self._retranslate_window()

    # ---- 构建页签 ----------------------------------------------------------
    def _status(self, msg):
        self.statusBar().showMessage(msg, 8000)

    def _build_tabs(self):
        self.project_panel = ProjectPanel(self.state, self._status)
        self.run_panel = RunPanel(self.state, self._status)
        self.calib_panel = CalibPanel(self.state, self._status)
        self.map_panel = MapInteractPanel(self.state, self._status)
        self.charts_panel = ChartsPanel(self.state)
        self.tabs.addTab(self.project_panel, tr("① 工程与数据", "① Project · Data"))
        self.tabs.addTab(self.run_panel, tr("② 运行仿真与分析", "② Run · Analyze"))
        self.tabs.addTab(self.calib_panel, tr("③ 标定与验证", "③ Calibrate · Validate"))
        self.tabs.addTab(self.map_panel, tr("④ 交互地图与点源", "④ Interactive Map · Point Source"))
        self.tabs.addTab(self.charts_panel, tr("⑤ 概览图表", "⑤ Overview Charts"))
        # 阶段A 完成后自动切到地图页
        self.state.stageAReady.connect(self._goto_map)

    def _goto_map(self):
        self.tabs.setCurrentWidget(self.map_panel)

    # ---- 菜单 --------------------------------------------------------------
    def _build_menu(self):
        bar = self.menuBar()
        bar.clear()
        m = bar.addMenu(tr("工程", "Project"))
        a1 = QAction(tr("载入密云示例工程", "Load Miyun example"), self); a1.triggered.connect(self._load_example); m.addAction(a1)
        a2 = QAction(tr("打开工程…", "Open project…"), self); a2.triggered.connect(self.project_panel._open); m.addAction(a2)
        a3 = QAction(tr("保存工程…", "Save project…"), self); a3.triggered.connect(self.project_panel._save); m.addAction(a3)
        m.addSeparator()
        aq = QAction(tr("退出", "Quit"), self); aq.triggered.connect(self.close); m.addAction(aq)

        lang = bar.addMenu(tr("语言", "Language"))
        zh = QAction("中文", self); zh.setCheckable(True); zh.setChecked(not i18n.is_en())
        zh.triggered.connect(lambda: self._switch_language("zh")); lang.addAction(zh)
        en = QAction("English", self); en.setCheckable(True); en.setChecked(i18n.is_en())
        en.triggered.connect(lambda: self._switch_language("en")); lang.addAction(en)

        h = bar.addMenu(tr("帮助", "Help"))
        ab = QAction(tr("关于 / 方法学说明", "About / Methodology"), self)
        ab.triggered.connect(self._about); h.addAction(ab)

    # ---- 语言切换 ----------------------------------------------------------
    # 关键：保留 map_panel（含 QWebEngineView）实例，仅就地 retranslate；
    # 其余轻量面板可安全重建。避免重建 QWebEngineView 导致的崩溃。
    def _switch_language(self, lang):
        if (lang == "en") == i18n.is_en():
            return
        i18n.set_lang(lang)
        idx = self.tabs.currentIndex()
        try:
            self.state.disconnect()      # 断开所有面板(含 map_panel)的 state 连接
        except TypeError:
            pass
        # 移除全部页签（不删除 widget），随后只删除非地图面板
        while self.tabs.count():
            self.tabs.removeTab(0)
        for p in (self.project_panel, self.run_panel, self.calib_panel, self.charts_panel):
            p.setParent(None)
            p.deleteLater()
        # 重建非地图面板（其 __init__ 会重连 state）
        self.project_panel = ProjectPanel(self.state, self._status)
        self.run_panel = RunPanel(self.state, self._status)
        self.calib_panel = CalibPanel(self.state, self._status)
        self.charts_panel = ChartsPanel(self.state)
        # 地图面板保留实例：重连 state 信号
        self.map_panel.reconnect()
        # 重新加入页签（保持顺序）
        self.tabs.addTab(self.project_panel, tr("① 工程与数据", "① Project · Data"))
        self.tabs.addTab(self.run_panel, tr("② 运行仿真与分析", "② Run · Analyze"))
        self.tabs.addTab(self.calib_panel, tr("③ 标定与验证", "③ Calibrate · Validate"))
        self.tabs.addTab(self.map_panel, tr("④ 交互地图与点源", "④ Interactive Map · Point Source"))
        self.tabs.addTab(self.charts_panel, tr("⑤ 概览图表", "⑤ Overview Charts"))
        self.state.stageAReady.connect(self._goto_map)
        self._build_menu()
        self._retranslate_window()
        # 重新填充
        if self.state.project:
            self.project_panel._refresh_info()
            self.run_panel._populate_years()
        if self.state.sa is not None:
            self.calib_panel._fill_screening()
            self.charts_panel.refresh()
        self.map_panel.retranslate()     # 就地更新地图面板文本并重绘地图
        self.tabs.setCurrentIndex(max(0, min(idx, self.tabs.count() - 1)))
        self._status(tr("已切换语言。", "Language switched."))

    def _retranslate_window(self):
        self.setWindowTitle(tr("水环境容量与风险评估集成平台  WEC-Risk Platform v1.0",
                               "Water Environmental Capacity & Risk Platform  WEC-Risk v1.0"))

    # ---- 动作 --------------------------------------------------------------
    def _load_example(self):
        if not os.path.isdir(EXAMPLE_ROOT):
            QMessageBox.information(self, tr("示例工程", "Example"),
                                    tr(f"未找到示例目录：\n{EXAMPLE_ROOT}\n请在「① 工程与数据」页选择你的 SWAT 工程根目录。",
                                       f"Example folder not found:\n{EXAMPLE_ROOT}\nPick your SWAT project root in tab ①."))
            return
        try:
            proj = Project.detect(EXAMPLE_ROOT, scenario="Miyun_Calib_01", name="Miyun")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, tr("载入失败", "Load failed"), str(e))
            return
        self.project_panel.root_edit.setText(EXAMPLE_ROOT)
        self.state.set_project(proj)
        self._status(tr("已载入密云示例工程，请到「② 运行」页点击「运行分析链路」。",
                        "Miyun example loaded — go to tab ② and click ‘Run analysis pipeline’."))

    def _about(self):
        QMessageBox.information(self, tr("关于", "About"), tr(
            "<b>水环境容量与风险评估集成平台 v1.0</b><br><br>"
            "集成：SWAT 仿真编排 → 关键因子筛选 → 动态自适应标准 → 基础/实际水环境容量 → "
            "两类风险指数 → 高风险区/传输热点 → 交互可视化。<br><br>"
            "第一类风险=本地非点源/实际容量；第二类风险=上游流入通量/实际容量（两类互不重叠）。<br>"
            "工程化通用：任意 SWAT2012 工程可经自动探测载入，无研究区硬编码。",
            "<b>WEC-Risk Platform v1.0</b><br><br>"
            "Integrates: SWAT orchestration → key-factor screening → dynamic adaptive standard → "
            "base/actual water environmental capacity → two risk indices → high-risk areas/transmission "
            "hotspots → interactive visualization.<br><br>"
            "Risk-1 = local NPS / actual capacity; Risk-2 = upstream inflow flux / actual capacity "
            "(mutually exclusive).<br>Portable: any SWAT2012 project loads via auto-detect, no hardcoding."))
