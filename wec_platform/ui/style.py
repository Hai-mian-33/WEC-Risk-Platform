"""
style.py — 全局视觉样式 / global QSS theme
============================================
统一放大字号、现代化配色与控件留白。在 run_gui 中通过 apply_style(app) 应用。
"""
from PyQt5.QtGui import QFont

STYLESHEET = """
* { font-family: "Microsoft YaHei UI", "Segoe UI", "PingFang SC", sans-serif; }
QMainWindow, QWidget { background: #f4f6f9; color: #1f2933; font-size: 16px; }

/* 页签 */
QTabWidget::pane { border: 1px solid #d6dce5; border-radius: 8px; background: #ffffff; top: -1px; }
QTabBar::tab {
    background: #e7ecf3; color: #4a5568; padding: 10px 16px; margin-right: 3px;
    border-top-left-radius: 8px; border-top-right-radius: 8px;
    font-size: 15px; font-weight: 600;
}
QTabBar::tab:selected { background: #2b6cb0; color: #ffffff; }
QTabBar::tab:hover:!selected { background: #d3dded; }

/* 分组框 */
QGroupBox {
    border: 1px solid #d6dce5; border-radius: 8px; margin-top: 16px;
    padding: 14px 12px 12px 12px; background: #ffffff; font-size: 16px;
}
QGroupBox::title {
    subcontrol-origin: margin; subcontrol-position: top left; left: 12px;
    padding: 2px 8px; color: #2b6cb0; font-weight: 700; font-size: 17px;
}

/* 按钮 */
QPushButton {
    background: #2b6cb0; color: #ffffff; border: none; border-radius: 6px;
    padding: 9px 18px; font-size: 16px; font-weight: 600;
}
QPushButton:hover { background: #2c5282; }
QPushButton:pressed { background: #244e7a; }
QPushButton:disabled { background: #a0aec0; color: #edf2f7; }

/* 输入控件 */
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {
    border: 1px solid #cbd5e0; border-radius: 6px; padding: 7px 9px;
    background: #ffffff; font-size: 16px; selection-background-color: #2b6cb0; min-height: 22px;
}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus { border: 1px solid #2b6cb0; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { font-size: 16px; selection-background-color: #ebf4ff; selection-color: #2b6cb0; }

/* 表格 */
QTableWidget, QListWidget {
    border: 1px solid #d6dce5; border-radius: 6px; background: #ffffff;
    gridline-color: #e2e8f0; font-size: 16px;
}
QTableWidget::item, QListWidget::item { padding: 6px; }
QTableWidget::item:selected, QListWidget::item:selected { background: #bee3f8; color: #1a365d; }
QHeaderView::section {
    background: #edf2f7; color: #2d3748; padding: 9px; border: none;
    border-right: 1px solid #e2e8f0; font-weight: 600; font-size: 16px;
}

/* 文本框 / 日志 */
QPlainTextEdit, QTextEdit {
    border: 1px solid #d6dce5; border-radius: 6px; background: #ffffff;
    font-size: 15px; padding: 8px;
}
QPlainTextEdit { font-family: "Consolas", "Cascadia Mono", monospace; }

/* 进度条 */
QProgressBar {
    border: 1px solid #cbd5e0; border-radius: 6px; text-align: center;
    background: #edf2f7; height: 26px; font-weight: 600; font-size: 15px;
}
QProgressBar::chunk { background: #38a169; border-radius: 5px; }

/* 菜单 / 状态栏 */
QMenuBar { background: #2d3748; color: #edf2f7; font-size: 16px; }
QMenuBar::item { padding: 9px 16px; background: transparent; }
QMenuBar::item:selected { background: #2b6cb0; }
QMenu { background: #ffffff; border: 1px solid #cbd5e0; font-size: 16px; }
QMenu::item { padding: 8px 26px; }
QMenu::item:selected { background: #ebf4ff; color: #2b6cb0; }
QStatusBar { background: #e7ecf3; color: #2d3748; font-size: 15px; }
QLabel { font-size: 16px; }

/* 特殊对象 */
QLabel#hint {
    color: #2a4365; background: #ebf4ff; border: 1px solid #bee3f8;
    border-radius: 8px; padding: 12px 14px; font-size: 15px;
}
QLabel#detailTitle { font-size: 20px; font-weight: 700; color: #2b6cb0; padding: 2px 0 6px 0; }

QSplitter::handle { background: #d6dce5; }
QSplitter::handle:horizontal { width: 4px; }
QScrollBar:vertical { width: 13px; background: #edf2f7; }
QScrollBar::handle:vertical { background: #b7c2d0; border-radius: 6px; min-height: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
"""


def apply_style(app):
    app.setFont(QFont("Microsoft YaHei UI", 11))
    app.setStyleSheet(STYLESHEET)
