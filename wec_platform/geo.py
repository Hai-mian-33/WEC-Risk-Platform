"""
geo.py — 矢量加载与地理处理
=============================

读取 subs1.shp / riv1.shp，统一重投影到 EPSG:4326（Leaflet 底图坐标），
与计算结果按 SUB 合并，并生成供 folium 使用的 GeoJSON 与拓扑流向箭头。

依赖 geopandas（已在系统 Python 安装）。
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Tuple

import pandas as pd

WGS84 = "EPSG:4326"


def _read_to_wgs84(shp_path: str):
    import geopandas as gpd
    gdf = gpd.read_file(shp_path)
    if gdf.crs is None:
        # SWAT 工程常缺 .prj 元信息时，按 subs1.prj 已知 UTM50N 兜底
        gdf = gdf.set_crs("EPSG:32650", allow_override=True)
    return gdf.to_crs(WGS84)


def load_subbasins(project) -> "object":
    """子流域多边形（EPSG:4326），含 SUB / cen_lon / cen_lat 列。"""
    gdf = _read_to_wgs84(project.subs_shp)
    if "Subbasin" in gdf.columns:
        gdf["SUB"] = gdf["Subbasin"].astype(int)
    elif "SUB" not in gdf.columns:
        gdf["SUB"] = range(1, len(gdf) + 1)
    gdf["SUB"] = gdf["SUB"].astype(int)
    cen = gdf.geometry.representative_point()
    gdf["cen_lon"] = cen.x
    gdf["cen_lat"] = cen.y
    return gdf


def load_rivers(project) -> Optional["object"]:
    if not os.path.isfile(project.riv_shp):
        return None
    try:
        gdf = _read_to_wgs84(project.riv_shp)
        if "Subbasin" in gdf.columns:
            gdf["SUB"] = gdf["Subbasin"].astype(int)
        return gdf
    except Exception:
        return None


def merge_results(gdf, result_df: pd.DataFrame):
    """把计算结果列并入子流域 GeoDataFrame（按 SUB）。"""
    cols = [c for c in result_df.columns if c != "SUB"]
    return gdf.merge(result_df[["SUB"] + cols], on="SUB", how="left")


def centroids_map(gdf) -> Dict[int, Tuple[float, float]]:
    """SUB -> (lon, lat) 代表点，用于画流向箭头。"""
    return {int(r.SUB): (float(r.cen_lon), float(r.cen_lat)) for r in gdf.itertuples()}


def flow_arrows(gdf, topology: pd.DataFrame
                ) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """按 TO_SUB 在质心间生成 (起点, 终点) 经纬度对列表。"""
    cen = centroids_map(gdf)
    arrows = []
    for _, row in topology.iterrows():
        s, to = int(row["SUB"]), row["TO_SUB"]
        try:
            to = int(to)
        except (ValueError, TypeError):
            continue
        if s in cen and to in cen and to != -1:
            arrows.append((cen[s], cen[to]))
    return arrows


def bounds(gdf) -> List[List[float]]:
    """[[south, west], [north, east]] 供 folium fit_bounds。"""
    minx, miny, maxx, maxy = gdf.total_bounds
    return [[float(miny), float(minx)], [float(maxy), float(maxx)]]


def to_geojson(gdf) -> dict:
    """GeoDataFrame -> GeoJSON dict（NaN 转 None，便于 JS 处理）。"""
    gj = json.loads(gdf.to_json())
    return gj
