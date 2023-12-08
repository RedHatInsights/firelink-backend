# Use Fedora as the base image
FROM fedora:latest

# Install Python 3.10 and pipenv
RUN dnf -y install python3.10 python3-pip && \
    pip3 install pipenv

# Create a non-root user and switch to it
RUN useradd -m appuser

# Set the working directory in the container
WORKDIR /app

# Change ownership of the working directory to the non-root user
RUN chown appuser:appuser /app

# Switch to non-root user
USER appuser

# Copy the Pipfile and Pipfile.lock
COPY --chown=appuser:appuser Pipfile Pipfile.lock ./

# Install dependencies from the Pipfile
RUN pipenv install --deploy --ignore-pipfile

# Copy the rest of the application source code
COPY --chown=appuser:appuser . .

# Set the environment variables
ENV FLASK_APP server.py
ENV FLASK_RUN_HOST 0.0.0.0
ENV FLASK_RUN_PORT 8080

# Expose the port the app runs on
EXPOSE 8080

# Start Gunicorn and bind to port 8080
CMD ["pipenv", "run", "gunicorn", "-b", ":8080", "server:app"]
