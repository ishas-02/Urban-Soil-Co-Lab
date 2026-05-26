# ============================================================
# Soil Co-Lab — Streamlit container for UB CaaS (OpenShift)
# Base: Red Hat UBI 9 Python 3.11 (matches OpenShift's preferred S2I)
# ============================================================
FROM registry.access.redhat.com/ubi9/python-311:latest

# Metadata (shows up in OpenShift console)
LABEL io.k8s.description="Soil Co-Lab Streamlit application" \
      io.k8s.display-name="Soil Co-Lab" \
      io.openshift.expose-services="8501:http" \
      io.openshift.tags="streamlit,python,soil-co-lab"

# --- Why /opt/app-root/src? ---
# UBI's python image runs as a non-root user with HOME=/opt/app-root.
# This is REQUIRED on OpenShift, which forbids running as root.
WORKDIR /opt/app-root/src

# Which Streamlit app to run. Override via env var per deployment:
#   APP_FILE=src/dashboard.py    → dashboard
#   APP_FILE=src/xrf_tech.py     → XRF tech form
#   APP_FILE=src/field_entry.py  → field entry
#   APP_FILE=src/site_builder.py → site builder
#   APP_FILE=etl_manager.py      → ETL manager
ENV APP_FILE=src/xrf_tech.py \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# --- Briefly become root to copy files, then fix ownership and drop back ---
# OpenShift will refuse to run the final image as root; we only need root
# at build time so the COPY lands with correct ownership.
USER 0

# Install Python deps first (cached layer if requirements unchanged)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Ensure data dir exists and is writable by the non-root user (UID 1001, GID 0).
# In production this will be a PersistentVolume mount.
RUN mkdir -p /opt/app-root/src/data && \
    chown -R 1001:0 /opt/app-root/src && \
    chmod -R g+rwX /opt/app-root/src

# --- Drop back to non-root for runtime (REQUIRED by OpenShift) ---
USER 1001

# Streamlit's default port
EXPOSE 8501

# NOTE: We don't set HEALTHCHECK here — OpenShift uses its own readiness/liveness
# probes (configurable in the Deployment YAML), which override Dockerfile HEALTHCHECK.
# See DEPLOY.md for adding probes via the OpenShift console.

# Run whichever app APP_FILE points to
CMD ["sh", "-c", "streamlit run $APP_FILE --server.port=$STREAMLIT_SERVER_PORT --server.address=$STREAMLIT_SERVER_ADDRESS"]