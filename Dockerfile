# Stage 1: Build the React application
FROM fedora:38 as react-build

# Install Node.js
RUN dnf -y update && dnf -y install nodejs

# Set the working directory for the React app
WORKDIR /app/firelink-ui

# Copy package.json and package-lock.json (or yarn.lock) for React app
COPY firelink-ui/package*.json ./

# Install React app dependencies
RUN npm install

# Copy the React app source code
COPY firelink-ui/ ./

ENV NODE_OPTIONS=--max-old-space-size=4096

# Build the React app
RUN npm run build

# Stage 2: Set up the Flask application
FROM fedora:38 as flask-app

# Install dependencies for pyenv
RUN dnf -y update && \
    dnf -y groupinstall 'Development Tools' && \
    dnf -y install git zlib-devel bzip2 bzip2-devel readline-devel sqlite sqlite-devel openssl-devel tk-devel libffi-devel xz-devel wget

# Install oc CLI
RUN curl -L https://mirror.openshift.com/pub/openshift-v4/clients/oc/latest/linux/oc.tar.gz | tar -xz -C /usr/local/bin

# Install pyenv
RUN git clone https://github.com/pyenv/pyenv.git ~/.pyenv
ENV PYENV_ROOT /root/.pyenv
ENV PATH $PYENV_ROOT/shims:$PYENV_ROOT/bin:$PATH

# Install Python using pyenv (e.g., Python 3.10.5)
RUN pyenv install 3.10.5 && \
    pyenv global 3.10.5

# Install pipenv
RUN pip install pipenv

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the Pipfile and Pipfile.lock into the container
COPY Pipfile Pipfile.lock ./

# Install the Python dependencies
RUN pipenv install --deploy --ignore-pipfile

# Copy the Flask app source code
COPY . .

# Copy the React build from the first stage
COPY --from=react-build /app/firelink-ui/build /usr/src/app/webroot

# Install Gunicorn
RUN pipenv install gunicorn

# Make port 80 available to the world outside this container
EXPOSE 80

# Start Gunicorn and bind to port 80
CMD ["pipenv", "run", "gunicorn", "-b", ":8080", "server:app"]
