# # # """
# # # groundsense_config.py — Single source of truth for the GroundSense project.

# # # Place this file in src/ alongside dashboard.py, data.py, etc.
# # # All other files import from here.
# # # """

# # # import math
# # # import json
# # # import os


# # # # ──────────────────────────────────────────────
# # # #  NYSH LEAD THRESHOLDS  (New York Soil Health)
# # # # ──────────────────────────────────────────────

# # # NYSH_TIERS = [
# # #     {"label": "Safe (< 63 ppm)",           "color": "#2ecc71", "floor":   0, "ceiling":  63},
# # #     {"label": "Elevated (63-99 ppm)",       "color": "#f1c40f", "floor":  63, "ceiling": 100},
# # #     {"label": "Contaminated (100-199 ppm)", "color": "#e67e22", "floor": 100, "ceiling": 200},
# # #     {"label": "High (200-399 ppm)",         "color": "#e74c3c", "floor": 200, "ceiling": 400},
# # #     {"label": "Hazard (400+ ppm)",          "color": "#800000", "floor": 400, "ceiling": float("inf")},
# # # ]

# # # NYSH_COLORS = {t["label"]: t["color"] for t in NYSH_TIERS}
# # # NYSH_COLORS["Unknown"] = "#808080"
# # # NYSH_ORDER = [t["label"] for t in NYSH_TIERS]


# # # def get_nysh_category(ppm):
# # #     """Return (label, hex_color) for a given Lead PPM value."""
# # #     if ppm is None or (isinstance(ppm, float) and math.isnan(ppm)):
# # #         return "Unknown", "#808080"
# # #     try:
# # #         ppm = float(ppm)
# # #     except (TypeError, ValueError):
# # #         return "Unknown", "#808080"
# # #     for tier in NYSH_TIERS:
# # #         if ppm < tier["ceiling"]:
# # #             return tier["label"], tier["color"]
# # #     return NYSH_TIERS[-1]["label"], NYSH_TIERS[-1]["color"]


# # # def get_nysh_label(ppm):
# # #     return get_nysh_category(ppm)[0]


# # # def get_nysh_color(ppm):
# # #     return get_nysh_category(ppm)[1]


# # # # ──────────────────────────────────────────────
# # # #  LOD (Limit of Detection) POLICY
# # # # ──────────────────────────────────────────────
# # # LOD_POLICY = "nan"
# # # LOD_HALF_VALUE = 5.0

# # # def resolve_lod(raw_value):
# # #     """Convert a raw LeadPPM cell (which may be '<LOD') to float or None."""
# # #     if isinstance(raw_value, str) and "<LOD" in raw_value.upper():
# # #         if LOD_POLICY == "zero":
# # #             return 0.0
# # #         elif LOD_POLICY == "half_lod":
# # #             return LOD_HALF_VALUE
# # #         else:
# # #             return None
# # #     try:
# # #         return float(raw_value)
# # #     except (TypeError, ValueError):
# # #         return None


# # # # ──────────────────────────────────────────────
# # # #  SPHERICAL TRIGONOMETRY — GPS OFFSET CALCULATOR
# # # # ──────────────────────────────────────────────
# # # R_EARTH_FT = 20_925_721.78

# # # def calculate_coordinate(start_lat, start_lon, offset_north_ft, offset_east_ft):
# # #     """Given a GPS anchor and a Cartesian offset in feet, return (lat, lon)."""
# # #     delta_lat = (offset_north_ft / R_EARTH_FT) * (180 / math.pi)
# # #     lat_radians = start_lat * (math.pi / 180)
# # #     delta_lon = (offset_east_ft / (R_EARTH_FT * math.cos(lat_radians))) * (180 / math.pi)
# # #     return start_lat + delta_lat, start_lon + delta_lon


# # # # ──────────────────────────────────────────────
# # # #  SITE CONFIG LOADER
# # # # ──────────────────────────────────────────────

# # # def load_site_configs(config_path=None):
# # #     """Load site_configs.json. Returns a dict keyed by address."""
# # #     if config_path is None:
# # #         config_path = os.path.join(
# # #             os.path.dirname(os.path.abspath(__file__)),
# # #             "..", "data", "site_configs", "site_configs.json"
# # #         )
# # #     if not os.path.exists(config_path):
# # #         return {}
# # #     with open(config_path, "r") as f:
# # #         raw = json.load(f)
# # #     return {site["address"]: site for site in raw}

# # """
# # groundsense_config.py — Single source of truth for the GroundSense project.

# # Place this file in src/ alongside dashboard.py, data.py, etc.
# # All other files import from here.

# # UPDATED: 6-tier NYSH convention matching field reference chart.
# # """

# # import math
# # import json
# # import os


# # # ──────────────────────────────────────────────
# # #  NYSH LEAD THRESHOLDS (6-Tier)
# # # ──────────────────────────────────────────────

# # NYSH_TIERS = [
# #     {"label": "Background (< 63)",              "color": "#2ecc71", "floor":    0, "ceiling":   63},
# #     {"label": "Typical Urban (64-99)",           "color": "#a8d86b", "floor":   63, "ceiling":  100},
# #     {"label": "Elevated (100-199)",              "color": "#f1c40f", "floor":  100, "ceiling":  200},
# #     {"label": "Action Recommended (200-399)",    "color": "#e67e22", "floor":  200, "ceiling":  400},
# #     {"label": "High / Hazard (400-999)",         "color": "#e74c3c", "floor":  400, "ceiling": 1000},
# #     {"label": "Very High / Hazard (1000+)",      "color": "#800000", "floor": 1000, "ceiling": float("inf")},
# # ]

# # NYSH_COLORS = {t["label"]: t["color"] for t in NYSH_TIERS}
# # NYSH_COLORS["Unknown"] = "#808080"
# # NYSH_ORDER = [t["label"] for t in NYSH_TIERS]


# # def get_nysh_category(ppm):
# #     """Return (label, hex_color) for a given Lead PPM value."""
# #     if ppm is None or (isinstance(ppm, float) and math.isnan(ppm)):
# #         return "Unknown", "#808080"
# #     try:
# #         ppm = float(ppm)
# #     except (TypeError, ValueError):
# #         return "Unknown", "#808080"
# #     for tier in NYSH_TIERS:
# #         if ppm < tier["ceiling"]:
# #             return tier["label"], tier["color"]
# #     return NYSH_TIERS[-1]["label"], NYSH_TIERS[-1]["color"]


# # def get_nysh_label(ppm):
# #     return get_nysh_category(ppm)[0]


# # def get_nysh_color(ppm):
# #     return get_nysh_category(ppm)[1]


# # # ──────────────────────────────────────────────
# # #  LOD (Limit of Detection) POLICY
# # # ──────────────────────────────────────────────
# # LOD_POLICY = "nan"
# # LOD_HALF_VALUE = 5.0

# # def resolve_lod(raw_value):
# #     """Convert a raw LeadPPM cell (which may be '<LOD') to float or None."""
# #     if isinstance(raw_value, str) and "<LOD" in raw_value.upper():
# #         if LOD_POLICY == "zero":
# #             return 0.0
# #         elif LOD_POLICY == "half_lod":
# #             return LOD_HALF_VALUE
# #         else:
# #             return None
# #     try:
# #         return float(raw_value)
# #     except (TypeError, ValueError):
# #         return None


# # # ──────────────────────────────────────────────
# # #  SPHERICAL TRIGONOMETRY — GPS OFFSET CALCULATOR
# # # ──────────────────────────────────────────────
# # R_EARTH_FT = 20_925_721.78

# # def calculate_coordinate(start_lat, start_lon, offset_north_ft, offset_east_ft):
# #     """Given a GPS anchor and a Cartesian offset in feet, return (lat, lon)."""
# #     delta_lat = (offset_north_ft / R_EARTH_FT) * (180 / math.pi)
# #     lat_radians = start_lat * (math.pi / 180)
# #     delta_lon = (offset_east_ft / (R_EARTH_FT * math.cos(lat_radians))) * (180 / math.pi)
# #     return start_lat + delta_lat, start_lon + delta_lon


# # # ──────────────────────────────────────────────
# # #  SITE CONFIG LOADER
# # # ──────────────────────────────────────────────

# # def load_site_configs(config_path=None):
# #     """Load site_configs.json. Returns a dict keyed by address."""
# #     if config_path is None:
# #         config_path = os.path.join(
# #             os.path.dirname(os.path.abspath(__file__)),
# #             "..", "data", "site_configs", "site_configs.json"
# #         )
# #     if not os.path.exists(config_path):
# #         return {}
# #     with open(config_path, "r") as f:
# #         raw = json.load(f)
# #     return {site["address"]: site for site in raw}

# """
# groundsense_config.py — Single source of truth for the GroundSense project.

# Place this file in src/ alongside dashboard.py, data.py, etc.
# All other files import from here.

# UPDATED:
#   - 6-tier NYSH convention matching field reference chart.
#   - calculate_coordinate_rotated() — applies a site-level rotation_deg
#     before the spherical-trig offset conversion, so that grid positions
#     saved in site_builder stay consistent across dashboard, site_builder,
#     and etl_manager.
# """

# import math
# import json
# import os


# # ──────────────────────────────────────────────
# #  NYSH LEAD THRESHOLDS (6-Tier)
# # ──────────────────────────────────────────────

# NYSH_TIERS = [
#     {"label": "Background (< 63)",              "color": "#2ecc71", "floor":    0, "ceiling":   63},
#     {"label": "Typical Urban (64-99)",           "color": "#a8d86b", "floor":   63, "ceiling":  100},
#     {"label": "Elevated (100-199)",              "color": "#f1c40f", "floor":  100, "ceiling":  200},
#     {"label": "Action Recommended (200-399)",    "color": "#e67e22", "floor":  200, "ceiling":  400},
#     {"label": "High / Hazard (400-999)",         "color": "#e74c3c", "floor":  400, "ceiling": 1000},
#     {"label": "Very High / Hazard (1000+)",      "color": "#800000", "floor": 1000, "ceiling": float("inf")},
# ]

# NYSH_COLORS = {t["label"]: t["color"] for t in NYSH_TIERS}
# NYSH_COLORS["Unknown"] = "#808080"
# NYSH_ORDER = [t["label"] for t in NYSH_TIERS]


# def get_nysh_category(ppm):
#     """Return (label, hex_color) for a given Lead PPM value."""
#     if ppm is None or (isinstance(ppm, float) and math.isnan(ppm)):
#         return "Unknown", "#808080"
#     try:
#         ppm = float(ppm)
#     except (TypeError, ValueError):
#         return "Unknown", "#808080"
#     for tier in NYSH_TIERS:
#         if ppm < tier["ceiling"]:
#             return tier["label"], tier["color"]
#     return NYSH_TIERS[-1]["label"], NYSH_TIERS[-1]["color"]


# def get_nysh_label(ppm):
#     return get_nysh_category(ppm)[0]


# def get_nysh_color(ppm):
#     return get_nysh_category(ppm)[1]


# # ──────────────────────────────────────────────
# #  LOD (Limit of Detection) POLICY
# # ──────────────────────────────────────────────
# LOD_POLICY = "nan"
# LOD_HALF_VALUE = 5.0


# def resolve_lod(raw_value):
#     """Convert a raw LeadPPM cell (which may be '<LOD') to float or None."""
#     if isinstance(raw_value, str) and "<LOD" in raw_value.upper():
#         if LOD_POLICY == "zero":
#             return 0.0
#         elif LOD_POLICY == "half_lod":
#             return LOD_HALF_VALUE
#         else:
#             return None
#     try:
#         return float(raw_value)
#     except (TypeError, ValueError):
#         return None


# # ──────────────────────────────────────────────
# #  SPHERICAL TRIGONOMETRY — GPS OFFSET CALCULATOR
# # ──────────────────────────────────────────────
# R_EARTH_FT = 20_925_721.78


# def calculate_coordinate(start_lat, start_lon, offset_north_ft, offset_east_ft):
#     """Given a GPS anchor and a Cartesian offset in feet, return (lat, lon)."""
#     delta_lat = (offset_north_ft / R_EARTH_FT) * (180 / math.pi)
#     lat_radians = start_lat * (math.pi / 180)
#     delta_lon = (offset_east_ft / (R_EARTH_FT * math.cos(lat_radians))) * (180 / math.pi)
#     return start_lat + delta_lat, start_lon + delta_lon


# def rotate_point(x, y, angle_deg):
#     """Rotate a Cartesian (x=east, y=north) point by angle_deg counterclockwise.

#     Returns (x_rotated, y_rotated).
#     """
#     if not angle_deg:
#         return x, y
#     r = angle_deg * math.pi / 180
#     return (x * math.cos(r) - y * math.sin(r),
#             x * math.sin(r) + y * math.cos(r))


# def calculate_coordinate_rotated(start_lat, start_lon,
#                                    offset_north_ft, offset_east_ft,
#                                    rotation_deg=0):
#     """Rotation-aware coordinate calculator.

#     Applies `rotation_deg` to the (east, north) offset before the spherical
#     conversion. This is the canonical function all GroundSense renderers
#     should use when a site_config has a non-zero rotation_deg.

#     Parameters
#     ----------
#     start_lat, start_lon : float
#         Anchor GPS coordinates (decimal degrees).
#     offset_north_ft, offset_east_ft : float
#         Cartesian offset from the anchor, in feet.
#     rotation_deg : float
#         Counterclockwise rotation of the local grid frame (degrees).
#     """
#     if rotation_deg:
#         east_rot, north_rot = rotate_point(offset_east_ft, offset_north_ft, rotation_deg)
#     else:
#         east_rot, north_rot = offset_east_ft, offset_north_ft
#     return calculate_coordinate(start_lat, start_lon, north_rot, east_rot)


# # ──────────────────────────────────────────────
# #  SITE CONFIG LOADER
# # ──────────────────────────────────────────────

# def load_site_configs(config_path=None):
#     """Load site_configs.json. Returns a dict keyed by address."""
#     if config_path is None:
#         config_path = os.path.join(
#             os.path.dirname(os.path.abspath(__file__)),
#             "..", "data", "site_configs", "site_configs.json"
#         )
#     if not os.path.exists(config_path):
#         return {}
#     with open(config_path, "r") as f:
#         raw = json.load(f)
#     return {site["address"]: site for site in raw}

"""
groundsense_config.py — Single source of truth for the GroundSense project.

Place this file in src/ alongside dashboard.py, data.py, etc.
All other files import from here.

UPDATED:
  - 6-tier NYSH convention matching field reference chart.
  - calculate_coordinate_rotated() — applies a site-level rotation_deg
    before the spherical-trig offset conversion, so that grid positions
    saved in site_builder stay consistent across dashboard, site_builder,
    and etl_manager.
"""

import math
import json
import os


# ──────────────────────────────────────────────
#  NYSH LEAD THRESHOLDS (6-Tier)
# ──────────────────────────────────────────────

NYSH_TIERS = [
    {"label": "Background (< 63)",              "color": "#2ecc71", "floor":    0, "ceiling":   63},
    {"label": "Typical Urban (64-99)",           "color": "#a8d86b", "floor":   63, "ceiling":  100},
    {"label": "Elevated (100-199)",              "color": "#f1c40f", "floor":  100, "ceiling":  200},
    {"label": "Action Recommended (200-399)",    "color": "#e67e22", "floor":  200, "ceiling":  400},
    {"label": "High / Hazard (400-999)",         "color": "#e74c3c", "floor":  400, "ceiling": 1000},
    {"label": "Very High / Hazard (1000+)",      "color": "#800000", "floor": 1000, "ceiling": float("inf")},
]

NYSH_COLORS = {t["label"]: t["color"] for t in NYSH_TIERS}
NYSH_COLORS["Unknown"] = "#808080"
NYSH_ORDER = [t["label"] for t in NYSH_TIERS]


def get_nysh_category(ppm):
    """Return (label, hex_color) for a given Lead PPM value."""
    if ppm is None or (isinstance(ppm, float) and math.isnan(ppm)):
        return "Unknown", "#808080"
    try:
        ppm = float(ppm)
    except (TypeError, ValueError):
        return "Unknown", "#808080"
    for tier in NYSH_TIERS:
        if ppm < tier["ceiling"]:
            return tier["label"], tier["color"]
    return NYSH_TIERS[-1]["label"], NYSH_TIERS[-1]["color"]


def get_nysh_label(ppm):
    return get_nysh_category(ppm)[0]


def get_nysh_color(ppm):
    return get_nysh_category(ppm)[1]


# ──────────────────────────────────────────────
#  LOD (Limit of Detection) POLICY
# ──────────────────────────────────────────────
LOD_POLICY = "nan"
LOD_HALF_VALUE = 5.0


def resolve_lod(raw_value):
    """Convert a raw LeadPPM cell (which may be '<LOD') to float or None."""
    if isinstance(raw_value, str) and "<LOD" in raw_value.upper():
        if LOD_POLICY == "zero":
            return 0.0
        elif LOD_POLICY == "half_lod":
            return LOD_HALF_VALUE
        else:
            return None
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return None


# ──────────────────────────────────────────────
#  SPHERICAL TRIGONOMETRY — GPS OFFSET CALCULATOR
# ──────────────────────────────────────────────
R_EARTH_FT = 20_925_721.78


def calculate_coordinate(start_lat, start_lon, offset_north_ft, offset_east_ft):
    """Given a GPS anchor and a Cartesian offset in feet, return (lat, lon)."""
    delta_lat = (offset_north_ft / R_EARTH_FT) * (180 / math.pi)
    lat_radians = start_lat * (math.pi / 180)
    delta_lon = (offset_east_ft / (R_EARTH_FT * math.cos(lat_radians))) * (180 / math.pi)
    return start_lat + delta_lat, start_lon + delta_lon


def rotate_point(x, y, angle_deg):
    """Rotate a Cartesian (x=east, y=north) point by angle_deg counterclockwise.

    Returns (x_rotated, y_rotated).
    """
    if not angle_deg:
        return x, y
    r = angle_deg * math.pi / 180
    return (x * math.cos(r) - y * math.sin(r),
            x * math.sin(r) + y * math.cos(r))


def calculate_coordinate_rotated(start_lat, start_lon,
                                   offset_north_ft, offset_east_ft,
                                   rotation_deg=0):
    """Rotation-aware coordinate calculator.

    Applies `rotation_deg` to the (east, north) offset before the spherical
    conversion. This is the canonical function all GroundSense renderers
    should use when a site_config has a non-zero rotation_deg.

    Parameters
    ----------
    start_lat, start_lon : float
        Anchor GPS coordinates (decimal degrees).
    offset_north_ft, offset_east_ft : float
        Cartesian offset from the anchor, in feet.
    rotation_deg : float
        Counterclockwise rotation of the local grid frame (degrees).
    """
    if rotation_deg:
        east_rot, north_rot = rotate_point(offset_east_ft, offset_north_ft, rotation_deg)
    else:
        east_rot, north_rot = offset_east_ft, offset_north_ft
    return calculate_coordinate(start_lat, start_lon, north_rot, east_rot)


# ──────────────────────────────────────────────
#  SITE CONFIG LOADER
# ──────────────────────────────────────────────

def load_site_configs(config_path=None):
    """Load site_configs.json. Returns a dict keyed by address."""
    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "data", "site_configs", "site_configs.json"
        )
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "r") as f:
        raw = json.load(f)
    return {site["address"]: site for site in raw}