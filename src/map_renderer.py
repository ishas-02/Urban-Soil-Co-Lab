"""
map_renderer.py — GroundSense shared map rendering module

Single source of truth for all site map rendering.
Used by site_builder.py (download buttons) and etl_manager.py (PPTX reports)
so that the resident sees IDENTICAL visuals regardless of origin.

Three public functions:
  - render_leaflet_html(site_config, master_df, show_numbers=False)
      → returns an HTML string (draggable satellite map, Leaflet)
  - render_static_png(site_config, master_df, output_path, show_numbers=True)
      → writes a dark-theme matplotlib PNG (no basemap, grid + values)
  - get_block_data(site_config, master_df)
      → helper: returns list of block dicts with merged real/mock ppm info
        (used internally, also useful if you want to build your own visuals)

Data policy
-----------
Cells with NO matching XRF data in Master_Data render as **gray "No Data"**.
We never silently fall back to mock_ppm values in exported maps — this
prevents placeholder numbers from appearing in official resident reports.
(If you want mock preview in site_builder UI, pass `use_mock_fallback=True`.)
"""

import json
import math
import os
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Polygon as MplPolygon

from groundsense_config import (
    get_nysh_category,
    NYSH_TIERS,
    calculate_coordinate_rotated,
    rotate_point,
    resolve_lod,
)


# ═══════════════════════════════════════════════════════════════
#  DATA MATCHING
# ═══════════════════════════════════════════════════════════════
NO_DATA_COLOR = "#808080"
NO_DATA_LABEL = "No Data"


def _match_sample_to_master(patterns, master_df):
    """Return average LeadPPM_Clean for any row whose SampleID contains
    one of the patterns. None if no match.
    """
    if not patterns or master_df is None or master_df.empty:
        return None
    for pat in patterns:
        if not pat:
            continue
        matches = master_df[
            master_df["SampleID"].str.contains(pat, case=False, na=False)
        ]
        if not matches.empty:
            avg = matches["LeadPPM_Clean"].mean()
            if pd.notna(avg):
                return float(avg)
    return None


def _ensure_clean_column(master_df):
    """Make sure master_df has a LeadPPM_Clean column. Returns a shallow copy."""
    if master_df is None or master_df.empty:
        return master_df
    if "LeadPPM_Clean" in master_df.columns:
        return master_df
    df = master_df.copy()
    df["LeadPPM_Clean"] = df["LeadPPM"].apply(resolve_lod)
    return df


def get_block_data(site_config, master_df, use_mock_fallback=False):
    """Merge site config blocks with master data and return a uniform list.

    Each returned dict has:
      id, corners (list of [x,y] in feet), cx, cy,
      ppm (float or None), color, label, has_real_data (bool)

    Set use_mock_fallback=True to use mock_ppm when real data is missing.
    Default False → missing cells are marked as "No Data" (gray).
    """
    master_df = _ensure_clean_column(master_df)

    blocks = []
    grid = site_config.get("grid_blocks", {})

    for bid, dims in grid.items():
        if bid.startswith("_"):
            continue
        patterns = dims.get("sample_id_patterns", [])
        real_ppm = _match_sample_to_master(patterns, master_df)

        if real_ppm is not None:
            ppm = real_ppm
            label, color = get_nysh_category(ppm)
            has_real = True
        elif use_mock_fallback and dims.get("mock_ppm"):
            ppm = float(dims["mock_ppm"])
            label, color = get_nysh_category(ppm)
            has_real = False
        else:
            ppm = None
            label, color = NO_DATA_LABEL, NO_DATA_COLOR
            has_real = False

        # Support custom polygons (e.g. L-shaped cells via _polygon)
        if "_polygon" in dims:
            corners = list(dims["_polygon"])
        else:
            corners = [
                [dims["sw_x"], dims["sw_y"]],
                [dims["ne_x"], dims["sw_y"]],
                [dims["ne_x"], dims["ne_y"]],
                [dims["sw_x"], dims["ne_y"]],
            ]

        cx = sum(c[0] for c in corners) / len(corners)
        cy = sum(c[1] for c in corners) / len(corners)

        blocks.append({
            "id": bid,
            "corners": corners,
            "cx": cx, "cy": cy,
            "ppm": ppm,
            "color": color,
            "label": label,
            "has_real_data": has_real,
        })

    points = []
    for pid, pt in site_config.get("point_samples", {}).items():
        if pid.startswith("_"):
            continue
        ox = pt.get("offset_x")
        oy = pt.get("offset_y")
        if ox is None or oy is None:
            continue
        patterns = pt.get("sample_id_patterns", [])
        real_ppm = _match_sample_to_master(patterns, master_df)

        if real_ppm is not None:
            ppm = real_ppm
            label, color = get_nysh_category(ppm)
            has_real = True
        else:
            ppm = None
            label, color = NO_DATA_LABEL, NO_DATA_COLOR
            has_real = False

        points.append({
            "id": pid,
            "ox": ox, "oy": oy,
            "ppm": ppm,
            "color": color,
            "label": label,
            "has_real_data": has_real,
        })

    return blocks, points


# ═══════════════════════════════════════════════════════════════
#  LEAFLET HTML RENDERER
# ═══════════════════════════════════════════════════════════════

def _build_legend_rows():
    """Generate the legend <div> rows from NYSH_TIERS (keeps colors in sync)."""
    rows = ""
    for t in NYSH_TIERS:
        rows += (
            '<div><span style="display:inline-block;width:11px;height:11px;'
            f'background:{t["color"]};border-radius:2px;margin-right:5px;'
            f'vertical-align:middle"></span>{t["label"]}</div>'
        )
    rows += (
        '<div><span style="display:inline-block;width:11px;height:11px;'
        f'background:{NO_DATA_COLOR};border-radius:2px;margin-right:5px;'
        f'vertical-align:middle"></span>{NO_DATA_LABEL}</div>'
    )
    return rows


def render_leaflet_html(site_config, master_df, show_numbers=False,
                        use_mock_fallback=False):
    """Generate a standalone HTML string for a draggable Leaflet map.

    Parameters
    ----------
    site_config : dict
        Single-site config entry (not the whole dict keyed by address).
    master_df : pd.DataFrame
        Master data with SampleID and LeadPPM columns.
    show_numbers : bool
        False → cell labels show only the cell ID (e.g. "A1").
        True  → cell labels show both the ID and the ppm value beneath it.
    use_mock_fallback : bool
        When True, missing XRF data uses the config's mock_ppm.
        Default False → missing cells render as "No Data" (gray).

    Returns
    -------
    str : Full HTML document ready to save to disk or embed via components.html()
    """
    anchor = site_config["anchor"]
    rotation_deg = site_config.get("rotation_deg", 0) or 0
    address = site_config.get("address", "Site")

    blocks, points = get_block_data(
        site_config, master_df, use_mock_fallback=use_mock_fallback
    )

    # Strip heavy fields before embedding in JS payload
    blocks_js = [
        {
            "id": b["id"],
            "corners": b["corners"],
            "cx": b["cx"], "cy": b["cy"],
            "ppm": b["ppm"] if b["ppm"] is not None else 0,
            "color": b["color"],
            "label": b["label"],
            "hasData": b["has_real_data"],
        }
        for b in blocks
    ]
    points_js = [
        {
            "id": p["id"],
            "ox": p["ox"], "oy": p["oy"],
            "ppm": p["ppm"] if p["ppm"] is not None else 0,
            "color": p["color"],
            "label": p["label"],
            "hasData": p["has_real_data"],
        }
        for p in points
    ]

    legend_rows = _build_legend_rows()
    title_meta = "Drag grid &middot; with values" if show_numbers else "Drag grid &middot; colors only"
    sn_flag = "true" if show_numbers else "false"

    # Pre-center the map slightly above the anchor for better framing
    center_lat, center_lon = calculate_coordinate_rotated(
        anchor["lat"], anchor["lon"],
        site_config.get("map_defaults", {}).get("center_offset_north_ft", 10),
        site_config.get("map_defaults", {}).get("center_offset_east_ft", 0),
        rotation_deg,
    )

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{address}_Soil Lead Screening Map</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
body{{margin:0;font-family:Arial,sans-serif}}
#map{{width:100%;height:100vh}}
.title-bar{{position:fixed;top:0;left:0;right:0;z-index:1001;
  background:rgba(12,15,20,0.95);padding:10px 20px;color:#e8eaed;
  border-bottom:2px solid #e67e22;display:flex;justify-content:space-between;
  align-items:center;font-size:14px}}
.title-bar b{{font-size:16px}}
.title-bar .meta{{font-size:12px;color:#7a8599}}
.legend{{position:fixed;bottom:30px;left:20px;z-index:1001;
  background:rgba(12,15,20,0.93);padding:14px 18px;border-radius:10px;
  color:#e8eaed;font-size:11px;line-height:1.8;
  border:1px solid rgba(255,255,255,0.08)}}
.legend b{{font-size:13px}}
.controls{{position:fixed;top:50px;right:20px;z-index:1001;
  background:rgba(12,15,20,0.93);padding:12px 16px;border-radius:10px;
  color:#e8eaed;font-size:11px;border:1px solid rgba(255,255,255,0.08);
  min-width:200px;transition:transform 0.3s,opacity 0.3s}}
.controls.hidden{{transform:translateX(260px);opacity:0;pointer-events:none}}
.controls b{{font-size:13px;color:#e67e22}}
.controls .hint{{font-size:9px;color:#7a8599}}
.controls .offset{{font-family:monospace;font-size:10px;color:#4ecdc4;
  margin-top:4px;background:rgba(78,205,196,0.08);padding:4px 8px;border-radius:4px}}
.controls button{{margin-top:4px;padding:3px 8px;border:1px solid rgba(255,255,255,0.15);
  border-radius:4px;background:rgba(78,205,196,0.12);color:#4ecdc4;
  cursor:pointer;font-size:10px}}
.controls button:hover{{background:rgba(78,205,196,0.25)}}
.rotate-row{{display:flex;gap:4px;align-items:center;margin-top:4px}}
.rotate-row button{{margin:0;padding:2px 6px;font-size:10px}}
.rotate-row span{{font-size:10px;color:#7a8599;min-width:30px;text-align:center}}
.toggle-btn{{position:fixed;top:55px;right:20px;z-index:1002;padding:6px 10px;
  border-radius:8px;border:1px solid rgba(255,255,255,0.15);
  background:rgba(12,15,20,0.9);color:#e67e22;cursor:pointer;font-size:11px;
  font-weight:bold;transition:opacity 0.3s}}
</style></head><body>
<div class="title-bar"><b>{address}_Soil Lead Screening Map</b>
<span class="meta">{title_meta}</span></div>
<div id="map"></div>
<div class="legend"><b>Lead Guidelines (ppm)</b><br>{legend_rows}</div>
<button class="toggle-btn" id="tb" onclick="tc()"
  style="opacity:0;pointer-events:none">&#9881;</button>
<div class="controls" id="cp"><b>Grid Controls</b>
<div class="hint">Click grid to drag</div>
<div class="rotate-row">
  <button onclick="rg(-5)">-5°</button>
  <button onclick="rg(-1)">-1°</button>
  <span id="rd">{rotation_deg}°</span>
  <button onclick="rg(1)">+1°</button>
  <button onclick="rg(5)">+5°</button>
</div>
<div class="offset" id="od">Offset: 0.0 E, 0.0 N</div>
<button onclick="rs()">Reset</button>
<button onclick="co()">Copy</button>
<button onclick="tc()" style="margin-top:8px;background:rgba(255,100,100,0.12);
  color:#ff6b6b;width:100%">Hide</button>
</div>
<script>
var AL={anchor["lat"]}, AO={anchor["lon"]}, SN={sn_flag};
var BL={json.dumps(blocks_js)};
var PT={json.dumps(points_js)};
var RF=20925721.78;
var CENTER_LAT={center_lat}, CENTER_LON={center_lon};

var pv=true;
function tc(){{pv=!pv;
  var p=document.getElementById('cp'),b=document.getElementById('tb');
  if(pv){{p.classList.remove('hidden');b.style.opacity='0';b.style.pointerEvents='none'}}
  else{{p.classList.add('hidden');b.style.opacity='1';b.style.pointerEvents='auto'}}
}}

var map=L.map('map',{{center:[CENTER_LAT,CENTER_LON],zoom:21,maxZoom:25}});
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}',
  {{attribution:'Esri',maxZoom:25,maxNativeZoom:19}}).addTo(map);

function f2ll(la,lo,n,e){{
  var dl=(n/RF)*(180/Math.PI);
  var dn=(e/(RF*Math.cos(la*Math.PI/180)))*(180/Math.PI);
  return [la+dl,lo+dn];
}}
function rp(x,y,a){{
  var r=a*Math.PI/180;
  return [x*Math.cos(r)-y*Math.sin(r), x*Math.sin(r)+y*Math.cos(r)];
}}

var oE=0,oN=0,rot={rotation_deg};
var gl=L.layerGroup().addTo(map);

function dg(){{
  gl.clearLayers();
  BL.forEach(function(b){{
    var ll=b.corners.map(function(c){{
      var r=rp(c[0],c[1],rot);
      return f2ll(AL,AO,r[1]+oN,r[0]+oE);
    }});
    var pl=L.polygon(ll,{{
      color:'white',weight:2,fillColor:b.color,fillOpacity:0.75
    }});
    var tp=(SN&&b.hasData)
      ? '<b>'+b.id+'</b><br>'+b.ppm.toFixed(0)+' ppm<br>'+b.label
      : '<b>'+b.id+'</b><br>'+b.label;
    pl.bindTooltip(tp);
    gl.addLayer(pl);
    var rc=rp(b.cx,b.cy,rot);
    var lp=f2ll(AL,AO,rc[1]+oN,rc[0]+oE);
    var lh;
    if(SN&&b.hasData){{
      lh='<div style="font-family:Arial;text-align:center;line-height:1.1;pointer-events:none">'+
         '<b style="font-size:10px;color:white;text-shadow:0 1px 3px rgba(0,0,0,0.8)">'+b.id+'</b><br>'+
         '<span style="font-size:9px;color:rgba(255,255,255,0.9);text-shadow:0 1px 2px rgba(0,0,0,0.7)">'+
         Math.round(b.ppm)+'</span></div>';
    }} else {{
      lh='<div style="font-family:Arial;text-align:center;pointer-events:none">'+
         '<b style="font-size:10px;color:white;text-shadow:0 1px 3px rgba(0,0,0,0.8)">'+b.id+'</b></div>';
    }}
    gl.addLayer(L.marker(lp,{{
      icon:L.divIcon({{className:'',html:lh,iconSize:[50,25],iconAnchor:[25,12]}}),
      interactive:false
    }}));
  }});

  PT.forEach(function(p){{
    var r=rp(p.ox,p.oy,rot);
    var ll=f2ll(AL,AO,r[1]+oN,r[0]+oE);
    var cm=L.circleMarker(ll,{{
      radius:8,color:'white',weight:2,
      fillColor:p.color,fillOpacity:0.85
    }});
    var tp=(SN&&p.hasData)
      ? '<b>'+p.id+'</b><br>'+p.ppm.toFixed(0)+' ppm<br>'+p.label
      : '<b>'+p.id+'</b><br>'+p.label;
    cm.bindTooltip(tp);
    gl.addLayer(cm);
  }});

  document.getElementById('od').textContent='Offset: '+oE.toFixed(1)+' E, '+oN.toFixed(1)+' N'+
    (rot?(' | '+rot+'°'):'');
  document.getElementById('rd').textContent=rot+'°';
}}

function rg(d){{rot+=d;dg();}}
function rs(){{oE=0;oN=0;rot={rotation_deg};dg();}}
function co(){{
  var t='East='+oE.toFixed(2)+', North='+oN.toFixed(2)+', Rot='+rot+'°';
  navigator.clipboard.writeText(t).then(function(){{alert(t);}});
}}

var iD=false,dL=null,dE=0,dN=0;
map.on('mousedown',function(e){{
  var f=false;
  gl.eachLayer(function(l){{
    if(l instanceof L.Polygon&&l.getBounds().contains(e.latlng)) f=true;
  }});
  if(f){{
    iD=true;dL=e.latlng;dE=oE;dN=oN;
    map.dragging.disable();
    map.getContainer().style.cursor='grabbing';
  }}
}});
map.on('mousemove',function(e){{
  if(!iD) return;
  oN=dN+(e.latlng.lat-dL.lat)*(Math.PI/180)*RF;
  oE=dE+(e.latlng.lng-dL.lng)*(Math.PI/180)*RF*Math.cos(AL*Math.PI/180);
  dg();
}});
map.on('mouseup',function(){{
  if(iD){{iD=false;map.dragging.enable();map.getContainer().style.cursor='';}}
}});

dg();
</script></body></html>
"""
    return html


# ═══════════════════════════════════════════════════════════════
#  STATIC PNG RENDERER (dark theme, matches screenshot exactly)
# ═══════════════════════════════════════════════════════════════

def render_static_png(site_config, master_df, output_path,
                       show_numbers=True, use_mock_fallback=False):
    """Render a dark-themed PNG map (no basemap) with optional value labels.

    Matches the "no basemap with numbers" screenshot style:
      - Dark background (#1a1c24)
      - Colored rounded cells with white IDs on dark pill
      - PPM values underneath each ID when show_numbers=True
      - Legend in bottom-right
      - Axis labels for East/North (ft)

    Rotation from site_config['rotation_deg'] is applied to all corners.
    """
    anchor = site_config["anchor"]
    rotation_deg = site_config.get("rotation_deg", 0) or 0
    address = site_config.get("address", "Site")

    blocks, points = get_block_data(
        site_config, master_df, use_mock_fallback=use_mock_fallback
    )

    bg = "#1a1c24"
    text_c = "white"
    edge_c = "white"

    fig, ax = plt.subplots(1, 1, figsize=(10, 7.5), facecolor=bg)
    ax.set_facecolor(bg)

    all_x, all_y = [], []

    for b in blocks:
        # Apply rotation to each corner in ft-space
        rotated_corners = [rotate_point(c[0], c[1], rotation_deg) for c in b["corners"]]

        if len(b["corners"]) == 4 and rotation_deg == 0:
            # Use FancyBboxPatch for axis-aligned rects (rounded corners)
            xs = [c[0] for c in rotated_corners]
            ys = [c[1] for c in rotated_corners]
            sx, sy = min(xs), min(ys)
            w, h = max(xs) - sx, max(ys) - sy
            patch = FancyBboxPatch(
                (sx, sy), w, h, boxstyle="round,pad=0.3",
                facecolor=b["color"], edgecolor=edge_c,
                linewidth=1.5, alpha=0.85,
            )
        else:
            # Fall back to a plain polygon for rotated / non-rectangular cells
            patch = MplPolygon(
                rotated_corners, closed=True,
                facecolor=b["color"], edgecolor=edge_c,
                linewidth=1.5, alpha=0.85,
            )

        ax.add_patch(patch)

        cx_r, cy_r = rotate_point(b["cx"], b["cy"], rotation_deg)
        cell_h = max(c[1] for c in b["corners"]) - min(c[1] for c in b["corners"])

        # Cell ID on dark pill
        ax.text(
            cx_r, cy_r, b["id"],
            ha="center", va="center",
            fontsize=10, fontweight="bold", color="white",
            bbox=dict(boxstyle="round,pad=0.25",
                      facecolor="black", alpha=0.5, edgecolor="none"),
        )

        # PPM value below ID when numbers are enabled AND data is real
        if show_numbers and b["has_real_data"] and b["ppm"] is not None:
            ax.text(
                cx_r, cy_r - cell_h * 0.28,
                f"{b['ppm']:.0f}",
                ha="center", va="center",
                fontsize=9, color="white", alpha=0.95,
            )

        for c in rotated_corners:
            all_x.append(c[0]); all_y.append(c[1])

    # Point samples
    for p in points:
        ox_r, oy_r = rotate_point(p["ox"], p["oy"], rotation_deg)
        ax.plot(
            ox_r, oy_r, marker="o", markersize=11,
            color=p["color"], markeredgecolor=edge_c, markeredgewidth=1.5,
        )
        ax.text(ox_r, oy_r + 2.5, p["id"], ha="center", va="bottom",
                 fontsize=8, color="#cccccc", fontstyle="italic")
        if show_numbers and p["has_real_data"] and p["ppm"] is not None:
            ax.text(ox_r, oy_r - 2.5, f"{p['ppm']:.0f}",
                     ha="center", va="top",
                     fontsize=7, color="white", fontweight="bold")
        all_x.append(ox_r); all_y.append(oy_r)

    # Anchor marker
    ax.plot(
        0, 0, marker="^", markersize=13, color="#ff4444",
        markeredgecolor=edge_c, markeredgewidth=1.5, zorder=10,
    )
    ax.text(0, -3, "Anchor", ha="center", va="top",
             fontsize=8, color="#ff6b6b", fontweight="bold")

    if all_x and all_y:
        pad = 8
        ax.set_xlim(min(all_x) - pad, max(all_x) + pad)
        ax.set_ylim(min(all_y) - pad, max(all_y) + pad)

    ax.set_aspect("equal")
    ax.set_xlabel("East (ft)", color="#888888", fontsize=10)
    ax.set_ylabel("North (ft)", color="#888888", fontsize=10)
    ax.tick_params(colors="#666666", labelsize=8)
    for spine in ax.spines.values():
        spine.set_color("#333333")

    ax.set_title(
        f"{address}_Soil Lead Screening Map",
        color=text_c, fontsize=13, fontweight="bold", pad=14,
    )

    # Legend in bottom-right
    legend_patches = [mpatches.Patch(color=t["color"], label=t["label"])
                      for t in NYSH_TIERS]
    legend_patches.append(mpatches.Patch(color=NO_DATA_COLOR, label=NO_DATA_LABEL))
    ax.legend(
        handles=legend_patches, loc="lower right", fontsize=7,
        framealpha=0.85, facecolor="#2a2d38", edgecolor="#444444",
        labelcolor="white",
    )

    plt.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    plt.savefig(output_path, dpi=200, bbox_inches="tight",
                 facecolor=bg, edgecolor="none")
    plt.close()
    return output_path