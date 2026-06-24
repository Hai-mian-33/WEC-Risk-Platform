"""
main.py — WEC-Risk Platform 入口
=================================

GUI 模式（默认）:
    python main.py
CLI 模式（无界面跑全链路 / 对账 / 批处理）:
    python main.py --cli --root "D:\\SWAT_Beijing\\SWAT_BEIJING" --year 2022
    python main.py --cli --project examples\\miyun_project.json --year 2022 --reconcile
"""
from __future__ import annotations

import argparse
import os
import sys


def run_cli(args) -> int:
    import pandas as pd
    from wec_platform.project import Project
    from wec_platform import pipeline

    if args.project:
        project = Project.load(args.project)
    elif args.root:
        project = Project.detect(args.root, scenario=args.scenario)
    else:
        print("CLI 需要 --project 或 --root", file=sys.stderr)
        return 2

    print(f"[工程] {project.name}  scenario={project.scenario}  "
          f"子流域={project.n_subbasins}  年份={project.years}")
    print(f"[校验] {project.validate() or '通过'}")

    def cb(msg, frac):
        print(f"  [{frac*100:5.1f}%] {msg}")

    print("\n=== 阶段A ===")
    sa = pipeline.run_stage_a(project, progress_cb=cb)

    print(f"\n=== 阶段B (year={args.year}) ===")
    df = pipeline.run_stage_b(project, sa, year=args.year)
    cols = ["SUB", "C_dynamic", "Wi_kg_d", "W_actual_kg_d", "LP",
            "TR", "RiskClass_LP", "RiskClass_TR",
            "IsTransmissionHotspot"]
    print(df[cols].head(15).round(3).to_string(index=False))
    print(f"\n传输热点子流域: {sorted(df[df['IsTransmissionHotspot']]['SUB'].tolist())}")

    if args.reconcile:
        _reconcile(project, df, args.year)
    return 0


def _reconcile(project, df, year):
    """与既有 risk_index_{pol}_{year}_corrected.csv 逐列比对。"""
    import pandas as pd
    code = project.pollutant.code
    for name in (f"risk_index_{code}_{year}_corrected.csv",
                 f"risk_index_{code}_{year}.csv"):
        ref_path = os.path.join(project.cache_dir, name)
        if os.path.isfile(ref_path):
            break
    else:
        print("\n[对账] 未找到参考 CSV，跳过。")
        return

    print(f"\n=== 对账 vs {os.path.basename(ref_path)} ===")
    ref = pd.read_csv(ref_path)
    merged = df.merge(ref, on="SUB", suffixes=("_new", "_ref"))
    # 注：第二风险已按专利式(8)改为 TR=Influx/W_actual，与旧 CumulativeRisk 定义不同，故不对账该列。
    # 实际容量与第一风险(LP)算法未变，应与既有发表结果逐列吻合。
    pairs = [
        ("W_actual_kg_d", "W_actual_TN_kg_d"),
        ("LP", "LP_TN"),
        ("RiskClass_LP", "RiskClass_LP"),
    ]
    for new_c, ref_c in pairs:
        if new_c in merged and ref_c in merged:
            a, b = merged[new_c].astype(float), merged[ref_c].astype(float)
            denom = b.abs().replace(0, 1e-9)
            max_rel = ((a - b).abs() / denom).max()
            max_abs = (a - b).abs().max()
            flag = "OK " if max_abs < 1e-3 or max_rel < 1e-3 else "DIFF"
            print(f"  [{flag}] {new_c:18s} vs {ref_c:22s}  max|Δ|={max_abs:.4g}  maxRel={max_rel:.4g}")


def run_gui() -> int:
    # 必须在创建 QApplication 之前：① 设置 AA_ShareOpenGLContexts
    # ② 导入 QtWebEngineWidgets —— 否则内嵌地图(QWebEngineView)会报
    #   "QtWebEngineWidgets must be imported ... before a QCoreApplication instance"
    from PyQt5.QtCore import Qt, QCoreApplication
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    import PyQt5.QtWebEngineWidgets  # noqa: F401  (副作用导入，必须早于 QApplication)

    from PyQt5.QtWidgets import QApplication
    from wec_platform.ui.main_window import MainWindow
    from wec_platform.ui.style import apply_style
    app = QApplication(sys.argv)
    app.setApplicationName("WEC-Risk Platform")
    apply_style(app)
    win = MainWindow()
    win.show()
    return app.exec_()


def main():
    parser = argparse.ArgumentParser(description="WEC-Risk Platform")
    parser.add_argument("--cli", action="store_true", help="无界面 CLI 模式")
    parser.add_argument("--project", help="project.json 路径")
    parser.add_argument("--root", help="SWAT 工程根目录（自动探测）")
    parser.add_argument("--scenario", help="情景名（默认自动选择）")
    parser.add_argument("--year", type=int, default=None, help="分析年份（选择点源数据集）")
    parser.add_argument("--reconcile", action="store_true", help="与既有结果 CSV 对账")
    args = parser.parse_args()

    # 让 wec_platform 可被导入
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    if args.cli:
        sys.exit(run_cli(args))
    else:
        sys.exit(run_gui())


if __name__ == "__main__":
    main()
