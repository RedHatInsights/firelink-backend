# Firelink Backend
Backend REST API for the Firelink project: a web GUI for Bonfire.

## Config
You should set your oc token and server via the `OC_TOKEN` and `OC_SERVER` environment variables before starting the app on a cluster:
```
$ export OC_TOKEN="sha256~DEADBEEFDEADBEEFDEADBEEFDEADBEEF"
$ export OC_SERVER="https://api.secretlab.company.com:6443"
```
If you don't set these firelink-backend will assume you are already logged in with a local kubecontext and wont attempt a login to the OpenShift API.

## Development Setup
```bash
# Make sure you have pip and pipenv installed before these obviously
$ pipenv install
$ pipenv shell
$ make run
```
We also include a dev proxy to make doing development on the frontend and backend at the same time easier. You can start the dev proxy with:
```bash
$ make start-proxy
```
The backend will run on port 5000 and if you have firelink-frontend running locally it will run on port 3000. The dev proxy will run on port 8080 and send requests to the backend and frontend as required.