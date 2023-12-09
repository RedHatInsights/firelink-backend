# Use Red Hat Universal Base Image 8 with Python 3.11
FROM registry.access.redhat.com/ubi8/python-311:1-36

USER 0

# Enable the copr repo to get oc
RUN dnf -y install dnf-plugins-core && dnf -y copr enable yselkowitz/openshift

# Install Python 3 and necessary tools
RUN dnf -y install python3 python3-pip openshift-clients

# Create a non-root user
RUN useradd -m appuser

# Set the working directory in the container
WORKDIR /home/appuser

# Copy the rest of the application source code
COPY . .

# Install dependencies from the requirements.txt as root
RUN pip install -r requirements.txt

# Change ownership of the installed packages and working directory to appuser
RUN chown -R appuser:appuser /home/appuser /opt/app-root

# Set permissions to allow access to the OpenShift-assigned user
RUN chmod -R 777 /home/appuser

# Switch to non-root user
USER appuser

# Copy the application source code
COPY --chown=appuser:appuser . .

# Install dependencies from the requirements.txt
RUN pip install -r requirements.txt

# Set the environment variables
ENV FLASK_APP server.py
ENV FLASK_RUN_HOST 0.0.0.0
ENV FLASK_RUN_PORT 8000
ENV KUBECONFIG=/home/appuser/.kube/config

# Expose the port the app runs on
EXPOSE 8080

# Start Gunicorn and bind to port 8080
CMD ["gunicorn", "-b", ":8000", "server:app"]
