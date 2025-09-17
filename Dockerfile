# Use Red Hat Universal Base Image 9 with Python 3.11
FROM registry.access.redhat.com/ubi9/python-311:9.6-1756977307

# Root for tooling only
USER 0

# Keep tools lean (do NOT install python3/python3-pip here)
RUN dnf -y install dnf-plugins-core curl && dnf clean all

# OpenShift CLI (note: v3.11 is *ancient*; keep if you really need it)
RUN curl -sSL "https://github.com/openshift/origin/releases/download/v3.11.0/openshift-origin-client-tools-v3.11.0-0cbc58b-linux-64bit.tar.gz" \
      -o /tmp/oc.tar.gz \
 && tar zxf /tmp/oc.tar.gz -C /tmp/ \
 && mv /tmp/openshift-origin-client-tools-v3.11.0-0cbc58b-linux-64bit/oc /usr/bin/ \
 && rm -rf /tmp/oc.tar.gz /tmp/openshift-origin-client-tools-v3.11.0-0cbc58b-linux-64bit

# Create non-root user & workspace
RUN useradd -m appuser
WORKDIR /home/appuser

# Copy sources first (to leverage cache for requirements separately if you’d like)
COPY --chown=appuser:appuser requirements.txt .

# Install deps with the *correct* interpreter-bound pip
# (avoid system alt & any stray venvs)
RUN /usr/bin/python3.11 -m pip install -U pip setuptools wheel \
 && /usr/bin/python3.11 -m pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY --chown=appuser:appuser . .

# Drop root
USER appuser

# App env
ENV FLASK_APP="server.py" \
    FLASK_RUN_HOST="0.0.0.0" \
    FLASK_RUN_PORT="8000" \
    KUBECONFIG="/home/appuser/.kube/config"

EXPOSE 8000

# Prove at runtime we're on 3.11 (optional debug)
# RUN python -V && python -m pip --version

CMD ["gunicorn", "-k", "gevent", "-w", "1", "-b", ":8000", "server:app"]