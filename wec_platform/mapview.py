"""
mapview.py — 交互式专题地图生成（folium / Leaflet）/ Interactive thematic map
=================================================================================

为某一专题图层生成自包含 HTML：choropleth 着色、点击弹窗、传输热点、流向、点击桥接。

交互修复：传输热点不再用单独的透明叠加层（会拦截点击），改为把红色虚线边框
直接画进可点击的主图层样式；河网置于主图层之下；流向箭头(AntPath)置于最上但
设为 interactive=False，使点击穿透到主图层 —— 所有子流域均可点击。

双语：标题/图例/弹窗字段随 i18n 当前语言切换。
"""
from __future__ import annotations

import os
from typing import Dict

import numpy as np
import pandas as pd

from .config import RISK_CLASS_COLORS
from . import i18n
from .i18n import tr


# 图层定义：key -> (中文名, 英文名, 数据列, 类型, 单位)
LAYER_DEFS: Dict[str, dict] = {
    "C_dynamic":     {"zh": "动态自适应标准", "en": "Dynamic standard", "field": "C_dynamic", "kind": "seq", "unit": "mg/L"},
    "Wi_kg_d":       {"zh": "基础环境容量", "en": "Base capacity", "field": "Wi_kg_d", "kind": "div", "unit": "kg/d"},
    "W_actual_kg_d": {"zh": "实际环境容量", "en": "Actual capacity", "field": "W_actual_kg_d", "kind": "div", "unit": "kg/d"},
    "RiskClass_LP":  {"zh": "第一类风险·本地 (LP)", "en": "Risk-1 Local (LP)", "field": "RiskClass_LP", "kind": "risk", "unit": ""},
    "RiskClass_TR":  {"zh": "第二类风险·上游传输 (TR)", "en": "Risk-2 Upstream (TR)", "field": "RiskClass_TR", "kind": "risk", "unit": ""},
}


def layer_label(key: str) -> str:
    d = LAYER_DEFS.get(key, {})
    return tr(d.get("zh", key), d.get("en", key))


def _fmt(v, nd=3):
    try:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return "—"
        return f"{float(v):.{nd}f}"
    except (TypeError, ValueError):
        return str(v)


def add_display_columns(gdf, project):
    """为弹窗/提示预渲染格式化字符串列（随语言）。仅按编号；个别命名子流域附名称。"""
    g = gdf.copy()
    lang = i18n.get_lang()
    g["std_txt"] = [f"{_fmt(c)} mg/L（{i18n.gb_label(cls)}）" for c, cls in
                    zip(g.get("C_dynamic", []), g.get("Recommended_Class", [""] * len(g)))]
    g["strict_txt"] = [f"{_fmt(c)} mg/L" for c in g.get("C_strict", [np.nan] * len(g))]
    g["gb_txt"] = [i18n.gb_label(c) for c in g.get("GB_class", [""] * len(g))]
    g["wi_txt"] = [f"{_fmt(v, 1)} kg/d" for v in g.get("Wi_kg_d", [np.nan] * len(g))]
    g["wact_txt"] = [f"{_fmt(v, 1)} kg/d" for v in g.get("W_actual_kg_d", [np.nan] * len(g))]
    g["lp_txt"] = [f"{_fmt(v)}（{i18n.risk_label(c)}）" for v, c in
                   zip(g.get("LP", []), g.get("RiskClass_LP", [0] * len(g)))]
    g["tr_txt"] = [f"{_fmt(v)}（{i18n.risk_label(c)}）" for v, c in
                   zip(g.get("TR", []), g.get("RiskClass_TR", [0] * len(g)))]
    g["hot_txt"] = [(tr("⚠ 是", "⚠ Yes") if bool(h) else tr("否", "No"))
                    for h in g.get("IsTransmissionHotspot", [False] * len(g))]
    g["node_txt"] = [i18n.node_label(n) for n in g.get("Node_Type", [""] * len(g))]
    g["name_txt"] = [project.subbasin_name(int(s), lang) or "—" for s in g["SUB"]]
    g["SUB_txt"] = [str(int(s)) for s in g["SUB"]]
    return g


def _build_colormap(gdf, layer):
    import branca.colormap as cm
    kind, field = layer["kind"], layer["field"]
    vals = pd.to_numeric(gdf.get(field), errors="coerce").dropna()
    label = layer_label_from(layer)

    if kind == "risk":
        def color_fn(v):
            try:
                return RISK_CLASS_COLORS.get(int(v), "#cccccc")
            except (TypeError, ValueError):
                return "#cccccc"
        items = "".join(
            f'<div><i style="background:{RISK_CLASS_COLORS[k]}"></i>{i18n.risk_label(k)}</div>'
            for k in (1, 2, 3, 4, 5))
        return color_fn, f'<b>{label}</b>{items}'

    vmin = float(vals.min()) if len(vals) else 0.0
    vmax = float(vals.max()) if len(vals) else 1.0
    if vmin == vmax:
        vmax = vmin + 1.0
    if kind == "div" and vmin < 0 < vmax:
        m = max(abs(vmin), abs(vmax))
        cmap = cm.LinearColormap(["#a50026", "#f7f7f7", "#313695"], vmin=-m, vmax=m)
        cmap.caption = f'{label} ({layer["unit"]}) — ' + tr("负值=赤字", "negative = deficit")
    else:
        cmap = cm.LinearColormap(["#ffffcc", "#fd8d3c", "#bd0026"], vmin=vmin, vmax=vmax)
        cmap.caption = f'{label} ({layer["unit"]})'

    def color_fn(v):
        try:
            if v is None or np.isnan(float(v)):
                return "#cccccc"
            return cmap(float(v))
        except (TypeError, ValueError):
            return "#cccccc"
    return color_fn, cmap


def layer_label_from(layer: dict) -> str:
    return tr(layer.get("zh", ""), layer.get("en", ""))


def _add_base_tiles(fmap):
    """加入多套全球底图，中英双语：OSM(本地语言/中文) 与 CartoDB(英文/拉丁) 等，可在图层控件切换。
    默认底图随当前语言选择（英文→CartoDB Voyager；中文→OSM）。"""
    import folium
    osm = folium.TileLayer("OpenStreetMap", name=tr("OpenStreetMap（本地语言/中文）", "OpenStreetMap (local)"),
                           max_zoom=19)
    voyager = folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
        attr="© OpenStreetMap contributors © CARTO", subdomains="abcd", max_zoom=20,
        name=tr("CartoDB Voyager（英文/全球）", "CartoDB Voyager (English/global)"))
    positron = folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/rastertiles/light_all/{z}/{x}/{y}{r}.png",
        attr="© OpenStreetMap contributors © CARTO", subdomains="abcd", max_zoom=20,
        name=tr("CartoDB Positron（英文/浅色）", "CartoDB Positron (English/light)"))
    esri = folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles © Esri — World Imagery", name=tr("Esri 卫星影像（全球）", "Esri Satellite (global)"),
        max_zoom=19)
    # folium 中「最后加入」的底图初始显示为默认。英文默认用干净的 CartoDB Voyager；中文默认 OSM。
    order = [esri, positron, osm, voyager] if i18n.is_en() else [esri, positron, voyager, osm]
    for t in order:
        t.add_to(fmap)


def build_map_html(project, gdf, rivers, topology, layer_key: str,
                   out_html: str, year=None) -> str:
    import folium
    from folium.plugins import AntPath
    from . import geo

    layer = LAYER_DEFS.get(layer_key, LAYER_DEFS["RiskClass_TR"])
    pol = project.pollutant
    gdf = add_display_columns(gdf, project)
    color_fn, legend = _build_colormap(gdf, layer)
    field = layer["field"]
    # 传输热点只在「第二类风险·上游传输」图层上显示
    show_hotspots = (layer_key == "RiskClass_TR") and ("IsTransmissionHotspot" in gdf.columns)

    b = geo.bounds(gdf)
    center = [(b[0][0] + b[1][0]) / 2, (b[0][1] + b[1][1]) / 2]
    fmap = folium.Map(location=center, zoom_start=10, tiles=None, control_scale=True,
                      min_zoom=2, max_zoom=18, world_copy_jump=True)
    _add_base_tiles(fmap)              # 全球底图，中英双语可切换
    fmap.fit_bounds(b)

    # (1) 河网 —— 置于底层
    if rivers is not None:
        try:
            folium.GeoJson(rivers, name=tr("河网", "River network"),
                           style_function=lambda x: {"color": "#3a7bd5", "weight": 2, "opacity": 0.55},
                           ).add_to(fmap)
        except Exception:
            pass

    # (2) 拓扑流向（AntPath）—— 置于主图层「之下」，确保主图层最顶、所有子流域均可点击
    for (lon1, lat1), (lon2, lat2) in geo.flow_arrows(gdf, topology):
        AntPath([[lat1, lon1], [lat2, lon2]], color="#1f4eb0", weight=2.5,
                delay=1000, dash_array=[10, 20]).add_to(fmap)

    # (3) 主专题图层（最顶、可点击）—— 仅在第二类风险图层上，传输热点用醒目亮红粗虚线边框
    def style_function(feat):
        p = feat["properties"]
        is_hot = show_hotspots and bool(p.get("IsTransmissionHotspot"))
        return {"fillColor": color_fn(p.get(field)),
                "color": "#e60000" if is_hot else "#444444",
                "weight": 4.5 if is_hot else 0.7,
                "dashArray": "9,5" if is_hot else None,
                "fillOpacity": 0.66}

    def highlight_function(feat):
        return {"weight": 5.0, "color": "#000000", "fillOpacity": 0.85}

    all_fields = ["SUB_txt", "name_txt", "gb_txt", "std_txt", "strict_txt",
                  "wi_txt", "wact_txt", "lp_txt", "tr_txt", "node_txt", "hot_txt"]
    all_aliases = [tr("子流域", "Subbasin"), tr("名称", "Name"),
                   tr("GB类别", "GB class"), tr("动态标准", "Dynamic std"),
                   tr("原始(严)标准", "Strict std"), tr("基础容量", "Base cap."),
                   tr("实际容量", "Actual cap."), tr("第一类风险(本地)", "Risk-1 (local)"),
                   tr("第二类风险(上游)", "Risk-2 (upstream)"), tr("节点类型", "Node type"),
                   tr("传输热点", "Transmission hotspot")]
    fields = [f for f in all_fields if f in gdf.columns]
    aliases = [all_aliases[all_fields.index(f)] for f in fields]

    gj = folium.GeoJson(
        gdf.__geo_interface__, name=layer_label_from(layer),
        style_function=style_function, highlight_function=highlight_function,
        tooltip=folium.GeoJsonTooltip(fields=["SUB_txt"], aliases=[tr("子流域", "Subbasin")], sticky=True),
        popup=folium.GeoJsonPopup(fields=fields, aliases=aliases, labels=True, max_width=380),
    )
    gj.add_to(fmap)

    # (4) 传输热点显著标记：脉冲红环 + ⚠（仅第二类风险图层；pointer-events:none，不拦截点击）
    if show_hotspots:
        fmap.get_root().header.add_child(folium.Element("""
        <style>
        .wec-hotspot{position:relative;width:0;height:0;pointer-events:none;}
        .wec-hotspot .dot{position:absolute;left:-11px;top:-11px;width:22px;height:22px;border-radius:50%;
            background:rgba(230,0,0,0.9);border:2px solid #fff;box-shadow:0 0 0 rgba(230,0,0,0.7);
            animation:wecpulse 1.5s infinite;}
        .wec-hotspot .lbl{position:absolute;left:14px;top:-22px;background:#e60000;color:#fff;
            font:700 12px/1.4 sans-serif;padding:1px 6px;border-radius:4px;white-space:nowrap;}
        @keyframes wecpulse{0%{box-shadow:0 0 0 0 rgba(230,0,0,0.7);}
            70%{box-shadow:0 0 0 18px rgba(230,0,0,0);}100%{box-shadow:0 0 0 0 rgba(230,0,0,0);}}
        </style>"""))
        hot_lbl = tr("传输热点", "Hotspot")
        for r in gdf[gdf["IsTransmissionHotspot"].fillna(False).astype(bool)].itertuples():
            try:
                lat, lon = float(r.cen_lat), float(r.cen_lon)
            except (AttributeError, ValueError, TypeError):
                continue
            html = (f'<div class="wec-hotspot"><div class="dot"></div>'
                    f'<div class="lbl">⚠ {hot_lbl} {int(r.SUB)}</div></div>')
            folium.Marker([lat, lon], icon=folium.DivIcon(html=html, icon_size=(0, 0),
                          icon_anchor=(0, 0))).add_to(fmap)

    if isinstance(legend, str):
        _add_html_legend(fmap, legend)
    else:
        legend.add_to(fmap)
    if show_hotspots:
        _add_hotspot_note(fmap)
    folium.LayerControl(collapsed=False).add_to(fmap)
    _inject_bridge(fmap, gj.get_name())

    yr = (f'　{year}' + tr("年", "")) if year else ""
    polname = pol.name_cn if not i18n.is_en() else pol.code
    title = f'{layer_label_from(layer)}　{polname}{yr}'
    _add_title(fmap, title)

    fmap.save(out_html)
    return out_html


def _add_html_legend(fmap, inner_html: str):
    import folium
    html = f"""
    <div style="position: fixed; bottom: 24px; left: 12px; z-index: 9999;
        background: rgba(255,255,255,0.94); padding: 9px 13px; border-radius: 8px;
        border: 1px solid #aaa; font-size: 13px; line-height: 1.7; box-shadow: 0 2px 8px rgba(0,0,0,.15);">
      {inner_html}
      <style>.leaflet-container i {{ display:inline-block; width:13px; height:13px;
            margin-right:7px; border:1px solid #777; vertical-align:middle; border-radius:2px; }}</style>
    </div>"""
    fmap.get_root().html.add_child(folium.Element(html))


def _add_hotspot_note(fmap):
    import folium
    txt = tr("传输热点", "Transmission hotspot")
    html = f"""
    <div style="position: fixed; bottom: 24px; right: 12px; z-index: 9999;
        background: rgba(255,255,255,0.94); padding: 8px 12px; border-radius: 8px;
        border: 1px solid #aaa; font-size: 13px; box-shadow: 0 2px 8px rgba(0,0,0,.15);">
      <span style="display:inline-block;width:22px;height:0;border-top:3px dashed #d7191c;
        vertical-align:middle;margin-right:6px;"></span>{txt}
    </div>"""
    fmap.get_root().html.add_child(folium.Element(html))


def _add_title(fmap, title: str):
    import folium
    html = f"""
    <div style="position: fixed; top: 10px; left: 50%; transform: translateX(-50%);
        z-index: 9999; background: rgba(255,255,255,0.94); padding: 7px 18px;
        border-radius: 8px; border: 1px solid #aaa; font-size: 16px; font-weight: 700;
        box-shadow: 0 2px 8px rgba(0,0,0,.15);">{title}</div>"""
    fmap.get_root().html.add_child(folium.Element(html))


def _inject_bridge(fmap, geojson_var: str):
    import folium
    fmap.get_root().header.add_child(
        folium.Element('<script src="qrc:///qtwebchannel/qwebchannel.js"></script>'))
    script = f"""
    <script>
    (function() {{
      function setupChannel() {{
        try {{
          if (typeof QWebChannel !== 'undefined' && typeof qt !== 'undefined') {{
            new QWebChannel(qt.webChannelTransport, function(channel) {{
              window.pyBridge = channel.objects.pyBridge;
            }});
          }}
        }} catch (e) {{}}
      }}
      function bindClicks() {{
        try {{
          var gj = {geojson_var};
          if (!gj) {{ setTimeout(bindClicks, 300); return; }}
          gj.eachLayer(function(layer) {{
            layer.on('click', function(ev) {{
              var p = layer.feature && layer.feature.properties;
              if (p && window.pyBridge && window.pyBridge.subbasinClicked) {{
                window.pyBridge.subbasinClicked(parseInt(p.SUB));
              }}
            }});
          }});
        }} catch (e) {{ setTimeout(bindClicks, 300); }}
      }}
      setupChannel();
      setTimeout(bindClicks, 400);
    }})();
    </script>"""
    fmap.get_root().html.add_child(folium.Element(script))
