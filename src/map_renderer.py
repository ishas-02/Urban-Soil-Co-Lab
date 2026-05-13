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

Multi-yard support
------------------
When a site_config has a `yards` key (front/back), each block carries
its own anchor + rotation reference (via the `yard` field on the block).
get_block_data() embeds the resolved anchor_lat/anchor_lon/rotation_deg
directly into each returned block dict so renderers don't need to know
about the yards structure — they just use what's in the dict.

Legacy single-yard configs (no `yards` key) keep working unchanged:
every block resolves to the top-level anchor + rotation_deg.

For PPM matching: SampleIDs without "Front" or "Back" in them default
to the backyard (per project spec). When a block's zone is front_yard,
we additionally require the SampleID to contain "front" (case-insensitive)
to be a valid match — preventing backyard readings from coloring front
blocks. Backyard blocks accept SampleIDs with "back" OR no front/back
keyword at all.
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


def _sample_yard(sample_id: str) -> str:
    """Classify a SampleID into 'front' or 'back' (defaults to 'back').

    Per spec: SampleIDs without 'Front' or 'Back' (case-insensitive)
    default to backyard. This means legacy data without yard markers
    in the name will color back-yard blocks, never front.
    """
    if not isinstance(sample_id, str):
        return "back"
    s = sample_id.lower()
    if "front" in s:
        return "front"
    if "back" in s:
        return "back"
    return "back"  # default per spec


def _match_sample_to_master(patterns, master_df, block_yard=None):
    """Return average LeadPPM_Clean for any row whose SampleID contains
    one of the patterns. None if no match.

    If `block_yard` is provided ('front' or 'back'), only matches whose
    SampleID resolves to the same yard are counted. This prevents a
    backyard reading from accidentally coloring a front-yard block when
    their patterns happen to overlap.

    block_yard=None preserves legacy behavior (no zone filter).
    """
    if not patterns or master_df is None or master_df.empty:
        return None
    for pat in patterns:
        if not pat:
            continue
        matches = master_df[
            master_df["SampleID"].str.contains(pat, case=False, na=False)
        ]
        if block_yard is not None and not matches.empty:
            matches = matches[
                matches["SampleID"].apply(_sample_yard) == block_yard
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


def _resolve_yard_anchor_and_rotation(site_config, yard_key):
    """Look up the anchor + rotation for a given yard.

    Returns (anchor_dict, rotation_deg).

    If site_config has a `yards` block and yard_key is in it, returns
    that yard's anchor + rotation. Otherwise falls back to the top-level
    `anchor` + `rotation_deg` (legacy single-yard path).
    """
    yards = site_config.get("yards") or {}
    if yard_key and yard_key in yards and yards[yard_key]:
        y = yards[yard_key]
        return y.get("anchor") or site_config.get("anchor", {}), \
               y.get("rotation_deg", 0) or 0
    # Legacy / single-yard / unknown yard → fall back to top-level.
    return (site_config.get("anchor", {}),
            site_config.get("rotation_deg", 0) or 0)


def get_block_data(site_config, master_df, use_mock_fallback=False):
    """Merge site config blocks with master data and return a uniform list.

    Each returned dict has:
      id, cell_id, yard, corners (list of [x,y] in feet), cx, cy,
      anchor_lat, anchor_lon, rotation_deg,
      ppm (float or None), color, label, has_real_data (bool)

    The per-block anchor_lat/anchor_lon/rotation_deg fields are populated
    from the block's `yard` field via the site_config's `yards` block when
    present, otherwise from the top-level anchor + rotation_deg. This means
    callers don't have to know about the yards structure — every block
    knows how to project itself.

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
        # Yard the block belongs to: explicit `yard` field, else infer from
        # `zone` ("front_yard"/"backyard"), else None (legacy single-yard).
        block_yard = dims.get("yard")
        if block_yard is None:
            zone = (dims.get("zone") or "").lower()
            if zone == "front_yard":
                block_yard = "front"
            elif zone == "backyard":
                block_yard = "back"
            else:
                block_yard = None  # legacy: no yard-aware filtering

        real_ppm = _match_sample_to_master(patterns, master_df,
                                            block_yard=block_yard)

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

        # Resolve per-block anchor and rotation so renderers don't have to.
        anchor, rotation_deg = _resolve_yard_anchor_and_rotation(
            site_config, block_yard
        )

        blocks.append({
            "id": bid,
            "cell_id": dims.get("cell_id", bid),  # human-readable cell label
            "yard": block_yard,                    # 'front' / 'back' / None
            "corners": corners,
            "cx": cx, "cy": cy,
            "anchor_lat": anchor.get("lat", 0),
            "anchor_lon": anchor.get("lon", 0),
            "rotation_deg": rotation_deg,
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
        # Point samples can also be yard-tagged (site_builder adds 'yard' to
        # new ones). Auxiliary zones don't filter by yard.
        pt_yard = pt.get("yard")
        if pt_yard is None:
            zone = (pt.get("zone") or "").lower()
            if zone == "front_yard":
                pt_yard = "front"
            elif zone == "backyard":
                pt_yard = "back"
            else:
                pt_yard = None
        real_ppm = _match_sample_to_master(patterns, master_df,
                                            block_yard=pt_yard)

        if real_ppm is not None:
            ppm = real_ppm
            label, color = get_nysh_category(ppm)
            has_real = True
        else:
            ppm = None
            label, color = NO_DATA_LABEL, NO_DATA_COLOR
            has_real = False

        anchor, rotation_deg = _resolve_yard_anchor_and_rotation(
            site_config, pt_yard
        )

        points.append({
            "id": pid,
            "name": pt.get("name", pid),
            "yard": pt_yard,
            "ox": ox, "oy": oy,
            "anchor_lat": anchor.get("lat", 0),
            "anchor_lon": anchor.get("lon", 0),
            "rotation_deg": rotation_deg,
            "ppm": ppm,
            "color": color,
            "label": label,
            "has_real_data": has_real,
        })

    return blocks, points


def _build_legend_rows():
    """Build legend rows HTML for the Leaflet renderer."""
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


# ═══════════════════════════════════════════════════════════════
#  LEAFLET HTML RENDERER (matches site_builder dark theme)
# ═══════════════════════════════════════════════════════════════

def render_leaflet_html(site_config, master_df,
                         show_numbers=False, use_mock_fallback=False):
    """Render a draggable Leaflet map as a self-contained HTML string.

    Output is identical between site_builder.py's download buttons and
    the embedded preview pane.

    Parameters
    ----------
    site_config : dict
        Single-site config entry (not the whole dict keyed by site_id).
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
    site_id = site_config.get("site_id", "Site")
    legacy_anchor = site_config.get("anchor", {"lat": 0, "lon": 0})
    legacy_rotation = site_config.get("rotation_deg", 0) or 0

    blocks, points = get_block_data(
        site_config, master_df, use_mock_fallback=use_mock_fallback
    )

    # Strip heavy fields before embedding in JS payload. Include the
    # per-block anchor + rotation so JS can project each block correctly.
    blocks_js = [
        {
            "id": b["id"],
            "cell_id": b.get("cell_id", b["id"]),
            "yard": b.get("yard"),
            "corners": b["corners"],
            "cx": b["cx"], "cy": b["cy"],
            "anchor_lat": b["anchor_lat"],
            "anchor_lon": b["anchor_lon"],
            "rotation_deg": b["rotation_deg"],
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
            "name": p.get("name", p["id"]),
            "yard": p.get("yard"),
            "ox": p["ox"], "oy": p["oy"],
            "anchor_lat": p["anchor_lat"],
            "anchor_lon": p["anchor_lon"],
            "rotation_deg": p["rotation_deg"],
            "ppm": p["ppm"] if p["ppm"] is not None else 0,
            "color": p["color"],
            "label": p["label"],
            "hasData": p["has_real_data"],
        }
        for p in points
    ]

    # Unique anchor markers across yards.
    yards_block = site_config.get("yards") or {}
    anchor_markers = []
    if yards_block:
        for yk, y in yards_block.items():
            if not y:
                continue
            anchor_markers.append({
                "lat": y["anchor"].get("lat", 0),
                "lon": y["anchor"].get("lon", 0),
                "label": f"{yk.capitalize()} Anchor",
                "color": "#ffd166" if yk == "front" else "#ff4444",
            })
    else:
        anchor_markers.append({
            "lat": legacy_anchor.get("lat", 0),
            "lon": legacy_anchor.get("lon", 0),
            "label": legacy_anchor.get("marker_label", "Anchor"),
            "color": "#ff4444",
        })

    legend_rows = _build_legend_rows()
    title_meta = "Drag grid &middot; with values" if show_numbers else "Drag grid &middot; colors only"
    sn_flag = "true" if show_numbers else "false"

    # Pre-center the map: midpoint of all anchors (or single-anchor legacy).
    if anchor_markers:
        center_lat = sum(a["lat"] for a in anchor_markers) / len(anchor_markers)
        center_lon = sum(a["lon"] for a in anchor_markers) / len(anchor_markers)
        # Apply a small north offset for framing (same intent as the
        # original calculate_coordinate_rotated nudge).
        defaults = site_config.get("map_defaults", {})
        north_ft = defaults.get("center_offset_north_ft", 10)
        east_ft = defaults.get("center_offset_east_ft", 0)
        center_lat, center_lon = calculate_coordinate_rotated(
            center_lat, center_lon, north_ft, east_ft, legacy_rotation
        )
    else:
        center_lat = legacy_anchor.get("lat", 0)
        center_lon = legacy_anchor.get("lon", 0)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{site_id}_Soil Lead Screening Map</title>
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
<div class="title-bar"><b>{site_id}_Soil Lead Screening Map</b>
<span class="meta">{title_meta}</span></div>
<div id="map"></div>
<button id="tb" class="toggle-btn" onclick="tc()" style="opacity:0;pointer-events:none">⚙</button>
<div id="cp" class="controls">
  <b>Grid Position</b>
  <div class="hint">Drag grid to fine-tune</div>
  <div class="rotate-row">
    <button onclick="rg(-5)">−5°</button>
    <button onclick="rg(-1)">−1°</button>
    <span id="rd">{legacy_rotation}°</span>
    <button onclick="rg(1)">+1°</button>
    <button onclick="rg(5)">+5°</button>
  </div>
  <div class="offset" id="od">Offset: 0.0 E, 0.0 N</div>
  <button onclick="rs()">Reset</button>
  <button onclick="co()">Copy Position</button>
  <button onclick="tc()">Hide Panel</button>
</div>
<div class="legend"><b>Lead Guidelines (ppm)</b><br>{legend_rows}</div>
<script>
var SN={sn_flag};
var BL={json.dumps(blocks_js)};
var PT={json.dumps(points_js)};
var ANCHORS={json.dumps(anchor_markers)};
var RF=20925721.78;
var CENTER_LAT={center_lat}, CENTER_LON={center_lon};
var LEGACY_ROT={legacy_rotation};

var pv=true;
function tc(){{pv=!pv;
  var p=document.getElementById('cp'),b=document.getElementById('tb');
  if(pv){{p.classList.remove('hidden');b.style.opacity='0';b.style.pointerEvents='none'}}
  else{{p.classList.add('hidden');b.style.opacity='1';b.style.pointerEvents='auto'}}
}}

var map=L.map('map',{{center:[CENTER_LAT,CENTER_LON],zoom:21,maxZoom:25}});
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}',
  {{attribution:'Esri',maxZoom:25,maxNativeZoom:19}}).addTo(map);

// Plot each anchor (one per yard, or one for legacy)
ANCHORS.forEach(function(a){{
  L.marker([a.lat,a.lon],{{
    icon:L.divIcon({{
      className:'',
      html:'<div style="width:14px;height:14px;background:'+a.color+
           ';border:2px solid white;border-radius:50%;box-shadow:0 0 6px rgba(0,0,0,0.6)"></div>',
      iconSize:[14,14],iconAnchor:[7,7]
    }})
  }}).addTo(map).bindTooltip(a.label);
}});

function f2ll(la,lo,n,e){{
  var dl=(n/RF)*(180/Math.PI);
  var dn=(e/(RF*Math.cos(la*Math.PI/180)))*(180/Math.PI);
  return [la+dl,lo+dn];
}}
function rp(x,y,a){{
  var r=a*Math.PI/180;
  return [x*Math.cos(r)-y*Math.sin(r), x*Math.sin(r)+y*Math.cos(r)];
}}

// Global drag-offset overlay (legacy behavior: same offset applied to
// every block). Per-block anchor + rotation come from the block itself.
var oE=0,oN=0,rot=LEGACY_ROT;
var gl=L.layerGroup().addTo(map);

function dg(){{
  gl.clearLayers();
  BL.forEach(function(b){{
    // Each block is projected from ITS OWN anchor + rotation.
    // Apply the (block.rotation + UI rotation_delta) and the (UI drag offset).
    var blockRot = b.rotation_deg + rot;
    var ll=b.corners.map(function(c){{
      var r=rp(c[0],c[1],blockRot);
      return f2ll(b.anchor_lat,b.anchor_lon,r[1]+oN,r[0]+oE);
    }});
    var pl=L.polygon(ll,{{
      color:'white',weight:2,fillColor:b.color,fillOpacity:0.75
    }});
    var displayId = b.cell_id || b.id;
    var tp=(SN&&b.hasData)
      ? '<b>'+displayId+'</b><br>'+b.ppm.toFixed(0)+' ppm<br>'+b.label
      : '<b>'+displayId+'</b><br>'+b.label;
    pl.bindTooltip(tp);
    gl.addLayer(pl);
    var rc=rp(b.cx,b.cy,blockRot);
    var lp=f2ll(b.anchor_lat,b.anchor_lon,rc[1]+oN,rc[0]+oE);
    var lh;
    if(SN&&b.hasData){{
      lh='<div style="font-family:Arial;text-align:center;line-height:1.1;pointer-events:none">'+
         '<b style="font-size:10px;color:white;text-shadow:0 1px 3px rgba(0,0,0,0.8)">'+displayId+'</b><br>'+
         '<span style="font-size:9px;color:rgba(255,255,255,0.9);text-shadow:0 1px 2px rgba(0,0,0,0.7)">'+
         Math.round(b.ppm)+'</span></div>';
    }} else {{
      lh='<div style="font-family:Arial;text-align:center;pointer-events:none">'+
         '<b style="font-size:10px;color:white;text-shadow:0 1px 3px rgba(0,0,0,0.8)">'+displayId+'</b></div>';
    }}
    gl.addLayer(L.marker(lp,{{
      icon:L.divIcon({{className:'',html:lh,iconSize:[50,25],iconAnchor:[25,12]}}),
      interactive:false
    }}));
  }});

  PT.forEach(function(p){{
    var ptRot = p.rotation_deg + rot;
    var r=rp(p.ox,p.oy,ptRot);
    var ll=f2ll(p.anchor_lat,p.anchor_lon,r[1]+oN,r[0]+oE);
    var cm=L.circleMarker(ll,{{
      radius:8,color:'white',weight:2,
      fillColor:p.color,fillOpacity:0.85
    }});
    var dn = p.name || p.id;
    var tp=(SN&&p.hasData)
      ? '<b>'+dn+'</b><br>'+p.ppm.toFixed(0)+' ppm<br>'+p.label
      : '<b>'+dn+'</b><br>'+p.label;
    cm.bindTooltip(tp);
    gl.addLayer(cm);
  }});

  document.getElementById('od').textContent='Offset: '+oE.toFixed(1)+' E, '+oN.toFixed(1)+' N'+
    (rot?(' | '+rot+'°'):'');
  document.getElementById('rd').textContent=rot+'°';
}}

function rg(d){{rot+=d;dg();}}
function rs(){{oE=0;oN=0;rot=LEGACY_ROT;dg();}}
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
  // Use the FIRST anchor's latitude for the drag-vector calculation
  // (only used to compute the longitude delta correction — small
  // approximation error across yards is acceptable for nudging).
  var refLat = ANCHORS.length ? ANCHORS[0].lat : CENTER_LAT;
  oN=dN+(e.latlng.lat-dL.lat)*(Math.PI/180)*RF;
  oE=dE+(e.latlng.lng-dL.lng)*(Math.PI/180)*RF*Math.cos(refLat*Math.PI/180);
  dg();
}});
map.on('mouseup',function(){{
  if(iD){{
    iD=false;
    map.dragging.enable();
    map.getContainer().style.cursor='';
  }}
}});

dg();
</script>
</body></html>
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

    For multi-yard configs, each yard's blocks are plotted in feet-space
    relative to a common origin (their own anchor). Since the PNG uses
    feet axes (not lat/lon), blocks from different yards may overlap in
    coordinate space — that's expected when both yards measure from
    nearby fixed points. Each block is colored by its own zone, so the
    yards are still visually distinguishable. The anchor marker shows
    every yard's anchor as a colored triangle.
    """
    site_id = site_config.get("site_id", "Site")

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
        # Apply THIS block's rotation (from its own yard) to its corners.
        # In PNG coordinate space we don't need anchor offsets — every
        # yard's blocks are plotted relative to (0,0) in feet, just
        # rotated to match their stored rotation_deg.
        block_rot = b["rotation_deg"]
        rotated_corners = [rotate_point(c[0], c[1], block_rot)
                           for c in b["corners"]]

        if len(b["corners"]) == 4 and block_rot == 0:
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
            patch = MplPolygon(
                rotated_corners, closed=True,
                facecolor=b["color"], edgecolor=edge_c,
                linewidth=1.5, alpha=0.85,
            )

        ax.add_patch(patch)

        cx_r, cy_r = rotate_point(b["cx"], b["cy"], block_rot)
        cell_h = max(c[1] for c in b["corners"]) - min(c[1] for c in b["corners"])

        # Cell ID on dark pill — use human-readable cell_id, not internal id.
        display_id = b.get("cell_id", b["id"])
        ax.text(
            cx_r, cy_r, display_id,
            ha="center", va="center",
            fontsize=10, fontweight="bold", color="white",
            bbox=dict(boxstyle="round,pad=0.25",
                      facecolor="black", alpha=0.5, edgecolor="none"),
        )

        if show_numbers and b["has_real_data"] and b["ppm"] is not None:
            ax.text(
                cx_r, cy_r - cell_h * 0.28,
                f"{b['ppm']:.0f}",
                ha="center", va="center",
                fontsize=9, color="white", alpha=0.95,
            )

        for c in rotated_corners:
            all_x.append(c[0]); all_y.append(c[1])

    for p in points:
        pt_rot = p["rotation_deg"]
        ox_r, oy_r = rotate_point(p["ox"], p["oy"], pt_rot)
        ax.plot(
            ox_r, oy_r, marker="o", markersize=11,
            color=p["color"], markeredgecolor=edge_c, markeredgewidth=1.5,
        )
        display_name = p.get("name", p["id"])
        ax.text(ox_r, oy_r + 2.5, display_name, ha="center", va="bottom",
                 fontsize=8, color="#cccccc", fontstyle="italic")
        if show_numbers and p["has_real_data"] and p["ppm"] is not None:
            ax.text(ox_r, oy_r - 2.5, f"{p['ppm']:.0f}",
                     ha="center", va="top",
                     fontsize=7, color="white", fontweight="bold")
        all_x.append(ox_r); all_y.append(oy_r)

    # Anchor markers — one per yard if multi-yard, else legacy single anchor.
    yards_block = site_config.get("yards") or {}
    if yards_block:
        for yk in yards_block.keys():
            if not yards_block[yk]:
                continue
            yard_color = "#ffd166" if yk == "front" else "#ff4444"
            ax.plot(
                0, 0, marker="^", markersize=13, color=yard_color,
                markeredgecolor=edge_c, markeredgewidth=1.5, zorder=10,
            )
            ax.text(0, -3, f"{yk.capitalize()} Anchor",
                     ha="center", va="top",
                     fontsize=8, color=yard_color, fontweight="bold")
    else:
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
        f"{site_id}_Soil Lead Screening Map",
        color=text_c, fontsize=13, fontweight="bold", pad=14,
    )

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