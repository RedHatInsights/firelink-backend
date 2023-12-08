# Use Red Hat Universal Base Image 8 with Python 3.11
FROM registry.access.redhat.com/ubi8/python-311:1-36

USER 0

# Enable the copr repo to get oc
RUN dnf -y install dnf-plugins-core && dnf -y copr enable yselkowitz/openshift

# Install Python 3, pipenv, and necessary tools
RUN dnf -y install python3 python3-pip openshift-clients && \
    pip3 install pipenv

# Create a non-root user
RUN useradd -m appuser

# Set the working directory in the container
WORKDIR /home/appuser

# Change ownership of the working directory to the non-root user
RUN chown -R appuser:appuser /home/appuser

# Switch to non-root user
USER appuser

# Ensure it is using the local venv
ENV PIPENV_VENV_IN_PROJECT=1

# Copy the rest of the application source code
COPY --chown=appuser:appuser . .

# Install dependencies from the Pipfile
RUN pipenv install

# Set the environment variables
ENV FLASK_APP server.py
ENV FLASK_RUN_HOST 0.0.0.0
ENV FLASK_RUN_PORT 8080

# Expose the port the app runs on
EXPOSE 8080

# Start Gunicorn and bind to port 8080
CMD ["pipenv", "run", "gunicorn", "-b", ":8080", "server:app"]
