"""
state.py — 全局应用状态与后台工作线程
=========================================

AppState 持有当前工程、阶段A结果、几何与阶段B结果，并以信号通知各面板。
重计算分两类：
  - 阶段A / SWAT 运行（慢）-> 后台 QThread，进度/日志通过信号回传
  - 阶段B（点源/年份变更，毫秒级）-> 主线程同步执行后 emit resultsChanged
"""
from __future__ import annotations

import os
import subprocess
from typing import Optional

import pandas as pd
from PyQt5.QtCore import QObject, QThread, pyqtSignal

from .. import geo, pipeline
from ..i18n import tr
from ..project import Project


# ----------------------------------------------------------------------------
# 后台线程
# ----------------------------------------------------------------------------
class StageAWorker(QThread):
    progress = pyqtSignal(str, float)
    done = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, project: Project):
        super().__init__()
        self.project = project

    def run(self):
        try:
            sa = pipeline.run_stage_a(self.project,
                                      progress_cb=lambda m, f: self.progress.emit(m, f))
            self.done.emit(sa)
        except Exception as e:  # noqa: BLE001
            import traceback
            self.failed.emit(f"{e}\n{traceback.format_exc()}")


class SwatWorker(QThread):
    log = pyqtSignal(str)
    done = pyqtSignal(int)

    def __init__(self, exe_path: str, cwd: str):
        super().__init__()
        self.exe_path = exe_path
        self.cwd = cwd
        self._proc = None

    def run(self):
        try:
            self.log.emit(f"启动 SWAT: {self.exe_path}\n工作目录: {self.cwd}\n")
            self._proc = subprocess.Popen(
                [self.exe_path], cwd=self.cwd, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            for line in self._proc.stdout:
                self.log.emit(line.rstrip())
            self._proc.wait()
            self.done.emit(self._proc.returncode)
        except Exception as e:  # noqa: BLE001
            self.log.emit(f"[错误] {e}")
            self.done.emit(-1)

    def stop(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()


# ----------------------------------------------------------------------------
# 应用状态
# ----------------------------------------------------------------------------
class AppState(QObject):
    projectChanged = pyqtSignal()
    stageAStarted = pyqtSignal()
    stageAProgress = pyqtSignal(str, float)
    stageAReady = pyqtSignal()
    stageAFailed = pyqtSignal(str)
    resultsChanged = pyqtSignal()
    logMessage = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.project: Optional[Project] = None
        self.sa = None                       # StageAResult
        self.gdf_base = None                 # 子流域几何（WGS84）
        self.rivers = None
        self.result_df: Optional[pd.DataFrame] = None
        self.gdf_merged = None
        self.current_year: Optional[int] = None
        self.point_df: Optional[pd.DataFrame] = None
        self._worker = None

    # ---- 工程 -------------------------------------------------------------
    def set_project(self, project: Project):
        self.project = project
        self.sa = None
        self.gdf_base = None
        self.rivers = None
        self.result_df = None
        self.gdf_merged = None
        self.point_df = None
        ps_years = project.point_source_years
        self.current_year = ps_years[-1] if ps_years else (project.years[-1] if project.years else None)
        self.projectChanged.emit()
        self.logMessage.emit(tr(
            f"已载入工程: {project.name}（{project.scenario}），子流域 {project.n_subbasins}，"
            f"输出年份 {project.years}，含点源年份 {ps_years}",
            f"Project loaded: {project.name} ({project.scenario}), subbasins {project.n_subbasins}, "
            f"output years {project.years}, years with point source {ps_years}"))

    # ---- 阶段A ------------------------------------------------------------
    def start_stage_a(self):
        if self.project is None:
            return
        self.stageAStarted.emit()
        self._worker = StageAWorker(self.project)
        self._worker.progress.connect(self.stageAProgress)
        self._worker.done.connect(self._on_stage_a_done)
        self._worker.failed.connect(self.stageAFailed)
        self._worker.start()

    def _on_stage_a_done(self, sa):
        self.sa = sa
        self.logMessage.emit(tr("阶段A 完成（拓扑/因子/动态标准/基础容量/面源已就绪）。",
                                "Stage A done (topology/factors/standard/base capacity/NPS ready)."))
        self._ensure_geometry()
        self.point_df = None          # 用严格逐年点源自动判定可用性
        self.recompute_stage_b()
        self.stageAReady.emit()

    def _ensure_geometry(self):
        if self.gdf_base is None:
            self.gdf_base = geo.load_subbasins(self.project)
            self.rivers = geo.load_rivers(self.project)

    # ---- 阶段B ------------------------------------------------------------
    def set_year(self, year: Optional[int]):
        self.current_year = year
        self.point_df = None          # 切换年份清除手动覆盖，按该年专属点源自动判定
        if self.sa is not None:
            self.recompute_stage_b()

    def recompute_stage_b(self, point_df: Optional[pd.DataFrame] = None):
        if self.project is None or self.sa is None:
            return
        if point_df is not None:
            self.point_df = point_df
        self.result_df = pipeline.run_stage_b(self.project, self.sa,
                                              point_df=self.point_df,
                                              year=self.current_year)
        self._ensure_geometry()
        if self.gdf_base is not None:
            self.gdf_merged = geo.merge_results(self.gdf_base, self.result_df)
        self.resultsChanged.emit()

    def subbasin_row(self, sub_id: int) -> Optional[pd.Series]:
        if self.result_df is None:
            return None
        m = self.result_df[self.result_df["SUB"] == sub_id]
        return m.iloc[0] if not m.empty else None
