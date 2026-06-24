"""
bridge.py — 地图 JS <-> Python 通信桥
======================================

注册到 QWebChannel 的对象（名 'pyBridge'）。地图中点击子流域要素时，
JS 调用 pyBridge.subbasinClicked(sub)（一个 pyqtSlot），这里转发为 Qt
信号 clicked 供侧栏响应。槽名必须是 JS 端调用的名字。
"""
from __future__ import annotations

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot


class MapBridge(QObject):
    clicked = pyqtSignal(int)

    @pyqtSlot(int)
    def subbasinClicked(self, sub_id: int):  # noqa: N802 — JS 端按此名调用
        self.clicked.emit(int(sub_id))
