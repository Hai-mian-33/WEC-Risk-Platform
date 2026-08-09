"""
swat_io.py — SWAT 工程 I/O 解析层
===================================

提供对一个 SWAT2012 工程的纯函数式读取，全部以传入路径为准、零硬编码：

  - read_file_cio()      解析 file.cio 的 IYR/NBYR/NYSKIP/IPRINT -> 输出年份列表
  - parse_fig_topology() 解析 fig.fig 的河网拓扑 (复刻 extract_topology.py)
  - read_output_rch()    解析 output.rch 月度河段输出 (复刻 calc_env_capacity / calc_nps_flux)
  - read_output_sub()    解析 output.sub BIGSUB 行的面源产污 (复刻 calc_nps_flux)
  - read_dbf_df()        读取 .dbf -> DataFrame
  - read_subbasin_attrs()/read_river_geometry() 从 subs1.dbf / riv1.dbf 取几何属性

设计要点：基础容量 Wi 与面源滞留率沿用「多年平均」口径（与已发表脚本一致，
year=None 即全年份平均）；read_output_rch 额外支持按日历年过滤以备进阶使用。
"""
from __future__ import annotations

import calendar
import os
import re
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from dbfread import DBF

from .config import Pollutant


# ============================================================================
# file.cio —— 模拟期与输出年份
# ============================================================================
def read_file_cio(txtinout_dir: str) -> Dict:
    """解析 file.cio，返回 {iyr, nbyr, nyskip, iprint, output_years, monthly}。"""
    path = os.path.join(txtinout_dir, "file.cio")
    info = {"iyr": None, "nbyr": None, "nyskip": 0, "iprint": 0}
    if not os.path.isfile(path):
        return _finalize_cio(info)

    key_map = {"NBYR": "nbyr", "IYR": "iyr", "NYSKIP": "nyskip", "IPRINT": "iprint"}
    with open(path, "r", errors="ignore") as f:
        for line in f:
            for key, attr in key_map.items():
                if re.search(rf"\b{key}\b", line):
                    m = re.match(r"\s*([-\d.]+)", line)
                    if m:
                        try:
                            info[attr] = int(float(m.group(1)))
                        except ValueError:
                            pass
    return _finalize_cio(info)


def write_file_cio_nyskip(txtinout_dir: str, nyskip: int) -> bool:
    """把预热年数 NYSKIP 写回 file.cio（运行 SWAT 前调用，使预热生效）。成功返回 True。"""
    path = os.path.join(txtinout_dir, "file.cio")
    if not os.path.isfile(path):
        return False
    with open(path, "r", errors="ignore") as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if re.search(r"\bNYSKIP\b", line):
            # 保留原行的「| 注释」部分，仅替换前导数值，并维持右对齐风格
            comment = line.split("|", 1)[1] if "|" in line else "NYSKIP: number of years to skip"
            lines[i] = f"{int(nyskip):16d}    |{comment.rstrip()}\n" if "|" in line \
                else f"{int(nyskip):16d}    | {comment}\n"
            with open(path, "w") as wf:
                wf.writelines(lines)
            return True
    return False


def _finalize_cio(info: Dict) -> Dict:
    iyr = info.get("iyr")
    nbyr = info.get("nbyr")
    nyskip = info.get("nyskip") or 0
    if iyr and nbyr:
        start = iyr + nyskip
        end = iyr + nbyr - 1
        info["output_years"] = list(range(start, end + 1))
    else:
        info["output_years"] = []
    info["monthly"] = (info.get("iprint", 0) != 1)  # IPRINT=1 daily, 0/2 monthly/annual
    return info


def _strict_monthly_rows(raw: pd.DataFrame, entity_col: str, mon_col: str,
                         cio: Optional[Dict] = None,
                         years: Optional[List[int]] = None) -> pd.DataFrame:
    """Return only genuine monthly rows and assign calendar year/month.

    SWAT2012 appends annual summaries and one long-term summary for every
    reach/sub-basin.  A simple ``MON <= 12`` filter can admit the terminal
    summary (its token may look like month 11), so the final-paper workflow
    validates the ordered 12-month sequence and retains exactly
    ``12 * len(output_years)`` rows per unit before applying a year subset.
    """
    out = raw[pd.to_numeric(raw[mon_col], errors="coerce").between(1, 12)].copy()
    out[entity_col] = pd.to_numeric(out[entity_col], errors="raise").astype(int)
    output_years = list((cio or {}).get("output_years") or [])
    if output_years:
        expected = 12 * len(output_years)
        out["_SEQ"] = out.groupby(entity_col, sort=False).cumcount()
        counts = out.groupby(entity_col).size()
        if (counts < expected).any():
            bad = counts[counts < expected].to_dict()
            raise ValueError(f"{entity_col}: fewer than {expected} monthly rows: {bad}")
        out = out[out["_SEQ"] < expected].copy()
        out["YEAR"] = output_years[0] + out["_SEQ"] // 12
        out["MONTH"] = out["_SEQ"] % 12 + 1
        mon = pd.to_numeric(out[mon_col], errors="raise").astype(int)
        mismatch = out[mon != out["MONTH"]]
        if not mismatch.empty:
            sample = mismatch[[entity_col, mon_col, "YEAR", "MONTH"]].head(1).to_dict("records")
            raise ValueError(f"{entity_col}: monthly order check failed: {sample}")
        out["DAYS"] = [calendar.monthrange(int(y), int(m))[1]
                       for y, m in zip(out["YEAR"], out["MONTH"])]
        out = out.drop(columns=["_SEQ"])
        if years is not None:
            requested = {int(y) for y in years}
            unknown = requested.difference(output_years)
            if unknown:
                raise ValueError(f"Requested years are outside SWAT output years: {sorted(unknown)}")
            out = out[out["YEAR"].isin(requested)].copy()
        expected_kept = 12 * (len(years) if years is not None else len(output_years))
        kept = out.groupby(entity_col).size()
        if not (kept == expected_kept).all():
            raise ValueError(f"{entity_col}: strict monthly counts are not all {expected_kept}")
    else:
        # Without file.cio metadata, at least reject non-month values.  The
        # caller cannot request calendar-year filtering in this fallback.
        if years is not None:
            raise ValueError("Calendar-year filtering requires readable file.cio metadata")
        out["MONTH"] = pd.to_numeric(out[mon_col], errors="raise").astype(int)
        out["DAYS"] = 30.4166666667
    out["MON"] = out["MONTH"]
    return out.reset_index(drop=True)


# ============================================================================
# fig.fig —— 河网拓扑（复刻 extract_topology.py）
# ============================================================================
def parse_fig_topology(txtinout_dir: str) -> pd.DataFrame:
    """解析 fig.fig，返回列 [SUB, TO_SUB, UPSTREAMS]。TO_SUB=-1 表示出口。"""
    path = os.path.join(txtinout_dir, "fig.fig")
    hyd_map: Dict[int, tuple] = {}
    with open(path, "r", errors="ignore") as f:
        for line in f:
            parts = line.split()
            if not parts:
                continue
            cmd = parts[0].lower()
            try:
                if cmd == "subbasin":
                    hyd_map[int(parts[2])] = ("subbasin", int(parts[3]))
                elif cmd == "route":
                    hyd_map[int(parts[2])] = ("reach", int(parts[3]), int(parts[4]))
                elif cmd == "add":
                    hyd_map[int(parts[2])] = ("add", int(parts[3]), int(parts[4]))
            except (IndexError, ValueError):
                continue

    def get_inflows(hyd_id: int) -> List[int]:
        node = hyd_map.get(hyd_id)
        if node is None:
            return []
        if node[0] == "subbasin":
            return []
        if node[0] == "reach":
            return [node[1]]
        if node[0] == "add":
            return get_inflows(node[1]) + get_inflows(node[2])
        return []

    upstream_dict: Dict[int, List[int]] = {}
    for _ihyd, node in hyd_map.items():
        if node[0] == "reach":
            upstream_dict[node[1]] = get_inflows(node[2])

    downstream_map: Dict[int, Optional[int]] = {i: None for i in upstream_dict}
    for rch, ups in upstream_dict.items():
        for u in ups:
            downstream_map[u] = rch

    rows = []
    for sub in sorted(downstream_map.keys()):
        ups = upstream_dict.get(sub, [])
        down = downstream_map[sub]
        rows.append({
            "SUB": sub,
            "TO_SUB": down if down is not None else -1,
            "UPSTREAMS": str(ups) if ups else "[]",
        })
    return pd.DataFrame(rows)


# ============================================================================
# output.rch —— 河段月度输出
# ============================================================================
def read_output_rch(txtinout_dir: str, pollutant: Pollutant,
                     years: Optional[List[int]] = None,
                     cio: Optional[Dict] = None) -> pd.DataFrame:
    """读取 output.rch（仅月份 1-12 行）。

    返回每行一个 (SUB, MON[, YEAR]) 的 DataFrame，列：
      SUB, MON, FLOW_OUT, TOT_load, TN_IN, TN_OUT[, YEAR]
    years=None 时返回全部输出年份（多年平均口径）；否则按日历年过滤。
    """
    path = os.path.join(txtinout_dir, "output.rch")
    raw = pd.read_csv(path, sep=r"\s+", skiprows=9, header=None)

    p = pollutant
    # 直接用「原始整数列」构造结果，避免「总负荷列」与「进/出列」索引相同时（如 COD 以 CBOD_OUT
    # 同时作为总负荷与流出列）先 rename 再按整数索引取数导致的 KeyError。
    def _col_sum(cols):
        s = 0.0
        for c in cols:
            s = s + raw[c]
        return s

    out = pd.DataFrame({
        "SUB": raw[p.rch_sub_col],
        "MON": raw[p.rch_mon_col],
        "FLOW_OUT": raw[p.rch_flow_col],
        "TOT_load": raw[p.rch_totload_col],
        "TN_IN": _col_sum(p.rch_in_cols),
        "TN_OUT": _col_sum(p.rch_out_cols),
    })
    cio = cio or read_file_cio(txtinout_dir)
    return _strict_monthly_rows(out, "SUB", "MON", cio=cio, years=years)


def rch_annual_means(rch: pd.DataFrame, conc_clip_upper: Optional[float] = None) -> pd.DataFrame:
    """按 SUB 聚合：年均流量(mean) + 质量通量加权长期平均浓度(复刻 calc_env_capacity_TN_v2)。

    conc = Σ(TOT_load)·1000 / Σ(FLOW_OUT·86400·calendar_days)  [mg/L]
    conc_clip_upper 不为 None 时对浓度做上限截断（v2 取 7.0，研究区/污染物相关）。
    """
    g = rch.groupby("SUB").agg(total_flow=("FLOW_OUT", "sum"),
                               FLOW_OUT=("FLOW_OUT", "mean"),
                               total_N=("TOT_load", "sum")).reset_index()
    if "DAYS" in rch.columns:
        volume = (rch["FLOW_OUT"] * rch["DAYS"] * 86400.0).groupby(rch["SUB"]).sum()
        total_vol = g["SUB"].map(volume)
    else:
        total_vol = g["total_flow"] * 86400.0 * 30.4
    g["conc"] = np.where(total_vol > 0, (g["total_N"] * 1000.0) / total_vol, 0.0)
    if conc_clip_upper is not None:
        g["conc"] = g["conc"].clip(upper=conc_clip_upper)
    return g[["SUB", "FLOW_OUT", "conc"]]


def rch_retention(rch: pd.DataFrame) -> pd.DataFrame:
    """按 SUB 汇总 TN_IN/TN_OUT（复刻 calc_nps_flux 的 rch_flux）。"""
    flux = rch.groupby("SUB")[["TN_IN", "TN_OUT"]].sum().reset_index()
    return flux


# ============================================================================
# output.sub —— 面源产污（复刻 calc_nps_flux.py 的逐行解析）
# ============================================================================
def read_output_sub(txtinout_dir: str, pollutant: Pollutant,
                    sub_ids: List[int], years: Optional[List[int]] = None,
                    cio: Optional[Dict] = None) -> Tuple[Dict[int, float], int]:
    """解析 output.sub BIGSUB 行，返回 (sub -> 累加 kg/ha, months_count)。

    months_count 为单个子流域累加到的月份数（用于换算日均），复刻原脚本以 sub==first 计数。
    """
    path = os.path.join(txtinout_dir, "output.sub")
    p = pollutant
    loads = {int(s): 0.0 for s in sub_ids}
    count_target = min(int(s) for s in sub_ids) if sub_ids else 1
    rows = []

    with open(path, "r", errors="ignore") as f:
        for _ in range(9):
            next(f, None)
        for line in f:
            parts = line.split()
            if len(parts) >= 28 and parts[0] == "BIGSUB":
                try:
                    sub = int(parts[p.sub_id_col])
                    mon_token = parts[p.sub_mon_col]
                    # The terminal long-term-average token starts with
                    # ``11.0.`` and is not a true November observation.
                    mon_val = 0 if mon_token.startswith("11.0.") else int(mon_token.split(".")[0])
                except (ValueError, IndexError):
                    continue
                if 1 <= mon_val <= 12:
                    try:
                        yield_kg_ha = sum(float(parts[c]) for c in p.sub_yield_cols)
                    except (ValueError, IndexError):
                        continue
                    rows.append({"SUB": sub, "MON_RAW": mon_val, "YIELD_KG_HA": yield_kg_ha})
    if not rows:
        return loads, 0
    monthly = _strict_monthly_rows(
        pd.DataFrame(rows), "SUB", "MON_RAW",
        cio=cio or read_file_cio(txtinout_dir), years=years,
    )
    summed = monthly.groupby("SUB")["YIELD_KG_HA"].sum()
    for sub in loads:
        loads[sub] = float(summed.get(sub, 0.0))
    months_count = int((monthly["SUB"] == count_target).sum())
    return loads, months_count


# ============================================================================
# DBF / 矢量属性
# ============================================================================
def read_dbf_df(dbf_path: str, fields: Optional[List[str]] = None) -> pd.DataFrame:
    db = DBF(dbf_path, load=True, char_decode_errors="ignore")
    df = pd.DataFrame(iter(db))
    if fields:
        present = [c for c in fields if c in df.columns]
        df = df[present]
    return df


def read_river_geometry(shapes_dir: str) -> pd.DataFrame:
    """riv1.dbf -> [SUB, Len2, Wid2, Dep2]（复刻 calc_env_capacity 用法）。"""
    df = read_dbf_df(os.path.join(shapes_dir, "riv1.dbf"),
                     ["Subbasin", "Len2", "Wid2", "Dep2"])
    return df.rename(columns={"Subbasin": "SUB"})


def read_subbasin_attrs(shapes_dir: str) -> pd.DataFrame:
    """subs1.dbf -> [SUB, Area_ha, Slope_pct, Elev_m, Lat, Lon]。

    slope/elev 取 subs1.dbf 的 Slo1/Elev（已核对与 adaptive_standard_TN.csv 一致）。
    """
    df = read_dbf_df(os.path.join(shapes_dir, "subs1.dbf"))
    rename = {"Subbasin": "SUB", "Area": "Area_ha", "Slo1": "Slope_pct",
              "Elev": "Elev_m", "Lat": "Lat", "Long_": "Lon"}
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    for col in ["SUB", "Area_ha", "Slope_pct", "Elev_m", "Lat", "Lon"]:
        if col not in df.columns:
            df[col] = np.nan
    df["SUB"] = df["SUB"].astype(int)
    return df[["SUB", "Area_ha", "Slope_pct", "Elev_m", "Lat", "Lon"]]
