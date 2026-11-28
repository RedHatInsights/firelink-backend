# Red Hat Hardened Images - Python 3.12
# Multi-stage build: builder for dependencies and tools, distroless runtime

# Build stage — runs as the image default user (65532); non-root throughout
FROM registry.access.redhat.com/hi/python:3.12-builder@sha256:fc861c2a8af818138a1e2b75b1b2b2385cb057ac54a32955c295de96f6f1c3f9 AS build

# Install tar and oc CLI as root (needed for system paths), then switch to non-root
USER 0
RUN microdnf install -y tar gzip && microdnf clean all && \
    curl -sSL "https://mirror.openshift.com/pub/openshift-v4/clients/ocp/stable/openshift-client-linux.tar.gz" \
      -o /tmp/oc.tar.gz && \
    tar zxf /tmp/oc.tar.gz -C /tmp/ && \
    mv /tmp/oc /usr/local/bin/ && \
    rm -rf /tmp/oc.tar.gz /tmp/kubectl
USER 65532

WORKDIR /opt/app-root/src

# Create virtualenv and install dependencies
# CRITICAL: Use --chown to prevent buildah from re-owning the directory to 0:0
COPY --chown=65532:0 requirements.txt .
RUN python3.12 -m venv .venv && \
    .venv/bin/pip install -U pip setuptools wheel && \
    .venv/bin/pip install --no-cache-dir -r requirements.txt

# Runtime stage — distroless, non-root, no shell
FROM registry.access.redhat.com/hi/python:3.12@sha256:ee183db4fb43716fa1bc7a65e53fd9f82e338217a39e8424974cfb6d360c4fd2

WORKDIR /opt/app-root/src

# App env
ENV APP_ROOT=/opt/app-root \
    APP_SRC=/opt/app-root/src \
    HOME=/tmp \
    FLASK_APP="server.py" \
    FLASK_RUN_HOST="0.0.0.0" \
    FLASK_RUN_PORT="8000" \
    KUBECONFIG="$HOME/.kube/config" \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH=/opt/app-root/src/.venv/bin:$PATH

# Copy virtualenv from build stage (must be at same absolute path)
COPY --from=build --chown=65532:0 /opt/app-root/src/.venv/ .venv/

# Copy oc CLI from build stage
COPY --from=build --chown=65532:0 /usr/local/bin/oc /usr/local/bin/oc

# Copy application source
COPY --chown=65532:0 . .

EXPOSE 8000

# Distroless supports only CMD/ENTRYPOINT (no RUN, no shell)
CMD ["gunicorn", "-k", "gevent", "-w", "1", "--timeout", "600", "-b", ":8000", "server:app"]