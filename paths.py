"""
Centralized paths for the Soil Co-Lab apps.

Why this exists:
    Right now the apps compute REPO_ROOT/data inline in many places.
    On OpenShift we will eventually mount a PersistentVolume at /data
    (or wherever) and we want to flip ONE switch rather than edit
    40 lines across 5 apps.

Usage (in any app):
    from paths import DATA_DIR
    csv_path = DATA_DIR / "xrf_data" / "something.csv"

The DATA_DIR resolves in this priority order:
    1. SOIL_DATA_DIR environment variable (set in OpenShift Deployment)
    2. ../data relative to this file (local dev fallback)
"""
import os
from pathlib import Path

# Folder containing this file = repo root (since paths.py sits at top level)
_HERE = Path(__file__).resolve().parent

# 1. Honor an env var if present (this is how OpenShift will point at the PV)
_env_dir = os.environ.get("SOIL_DATA_DIR")
if _env_dir:
    DATA_DIR = Path(_env_dir)
else:
    # 2. Local-dev fallback: ../data relative to repo root
    DATA_DIR = _HERE / "data"

# Make sure it exists (no-op if it already does)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Convenience subpaths — add more here as needed
XRF_DATA_DIR = DATA_DIR / "xrf_data"
SITE_DATABASES_DIR = DATA_DIR / "site_databases"
SITE_CONFIGS_DIR = DATA_DIR / "site_configs"
XRF_CHEMISTRY_DIR = DATA_DIR / "XRF_Chemistry"
XRF_TECH_SITE_DIR = DATA_DIR / "XRF_Technician_Site_Data"
XRF_TECH_CLINIC_DIR = DATA_DIR / "XRF_Technician_Clinic_Data"
MASTER_DATA_DIR = DATA_DIR / "master_data"
GENERATED_REPORTS_DIR = DATA_DIR / "generated_reports"

# Ensure all subdirs exist so first-write doesn't crash
for _d in (XRF_DATA_DIR, SITE_DATABASES_DIR, SITE_CONFIGS_DIR,
          XRF_CHEMISTRY_DIR, XRF_TECH_SITE_DIR, XRF_TECH_CLINIC_DIR,
          MASTER_DATA_DIR, GENERATED_REPORTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)