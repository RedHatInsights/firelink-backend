# Use Red Hat Universal Base Image 8 with Python 3.11
FROM registry.access.redhat.com/ubi8/python-311:1-90.1742347049

USER 0

# Install Python 3 and necessary tools
RUN dnf -y install python3 python3-pip  dnf-plugins-core curl

# Install OpenShift CLI
RUN curl -s -L "https://github.com/openshift/origin/releases/download/v3.11.0/openshift-origin-client-tools-v3.11.0-0cbc58b-linux-64bit.tar.gz" -o /tmp/oc.tar.gz && \
    tar zxvf /tmp/oc.tar.gz -C /tmp/ && \ 
    mv /tmp/openshift-origin-client-tools-v3.11.0-0cbc58b-linux-64bit/oc /usr/bin/ && \
    rm -rf /tmp/oc.tar.gz /tmp/openshift-origin-client-tools-v3.11.0-0cbc58b-linux-64bit/

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
RUN chmod -R 777 /home/appuser /opt/app-root

# Switch to non-root user
USER appuser

# Ensure /usr/bin is in the PATH
ENV PATH="/usr/bin:${PATH}"

# Copy the application source code
COPY --chown=appuser:appuser . .

# Install dependencies from the requirements.txt
RUN pip install -r requirements.txt

# Set the environment variables
ENV FLASK_APP="server.py"
ENV FLASK_RUN_HOST="0.0.0.0"
ENV FLASK_RUN_PORT="8000"
ENV KUBECONFIG="/home/appuser/.kube/config"

# Expose the port the app runs on
EXPOSE 8000

# Start Gunicorn and bind to port 8080
CMD ["gunicorn", "-k", "gevent", "-w", "1", "-b", ":8000", "server:app"]
