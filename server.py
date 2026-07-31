"""Flask API server for Firelink"""
import base64
import json
import logging
import os
import sys

from flask import Flask, abort, jsonify, request
from flask_caching import Cache
from flask_cors import CORS
from flask_socketio import ConnectionRefusedError, SocketIO, emit

from firelink.apps import Apps
from firelink.flask_app_helpers import FlaskAppHelpers
from firelink.metrics import (
    PrometheusClusterMetrics,
    PrometheusNamespaceMetrics,
    PrometheusPodMetrics,
)
from firelink.openshift_resources import Namespace

DEFAULT_PORT = 5000

app = Flask(__name__)
cache = Cache(app, config={"CACHE_TYPE": "simple"})
socketio = SocketIO(
    app, cors_allowed_origins="*", ping_timeout=600, path="/api/firelink/socket.io"
)
port = int(os.getenv("PORT", str(DEFAULT_PORT)))
helpers = FlaskAppHelpers()

# Run one-time setup functions at startup. These perform initial login to
# OpenShift and create the global GraphQL client. This replaces the previous
# call further down to app.before_request as they don't seem to be Flask request
# hooks (they return None), so they should not be added to before_request_funcs.
# Previously, line 75 assigned them to before_request_funcs, which both caused
# TypeError: 'NoneType' object is not callable and wiped out decorator-registered
# hooks like require_identity() and log_request_info()
helpers.login_to_openshift()
helpers.create_gql_client()

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)

CORS(app)

def identity_requester():
    """Extract the caller's username from the gateway-injected
    x-rh-identity header. Returns None if absent or malformed; callers
    must treat None as unauthenticated. The client-supplied request
    body is never trusted for requester identity."""
    raw = request.headers.get("x-rh-identity")
    if not raw:
        return None
    try:
        ident = json.loads(base64.b64decode(raw))
        return ident.get("identity", {}).get("user", {}).get("username")
    except (ValueError, TypeError, json.JSONDecodeError):
        return None

# All /api/firelink/* endpoints act on the cluster with the privileged
# OC_TOKEN service-account. They must only be reachable through the
# Clowder/3scale gateway, which injects an x-rh-identity header for
# authenticated SSO callers. Reject any request that arrives without it.
# Set FIRELINK_DISABLE_AUTH=true only for local development against a
# personal cluster.
REQUIRE_IDENTITY = os.getenv("FIRELINK_DISABLE_AUTH", "false").lower() != "true"
IDENTITY_HEADER = "x-rh-identity"


@app.before_request
def require_identity():
    """Reject unauthenticated requests to /api/firelink/*."""
    if not REQUIRE_IDENTITY:
        return
    if not request.path.startswith("/api/firelink/"):
        return
    if not request.headers.get(IDENTITY_HEADER):
        logging.warning(
            "Rejected unauthenticated request: %s %s from %s",
            request.method,
            request.path,
            request.remote_addr,
        )
        abort(401, description="x-rh-identity header required")


@socketio.on("connect")
def socketio_require_identity():
    """Reject unauthenticated SocketIO connections."""
    if REQUIRE_IDENTITY and not request.headers.get(IDENTITY_HEADER):
        logging.warning(
            "Rejected unauthenticated SocketIO connection from %s", request.remote_addr
        )
        raise ConnectionRefusedError("x-rh-identity header required")


@app.before_request
def log_request_info():
    """Log request information"""
    logging.info(
        "Request: %s %s - %s", request.method, request.url, request.remote_addr
    )


@app.route("/health")
def health():
    """Health check endpoint"""
    return ("", 200) if FlaskAppHelpers().health() else ("", 500)


@app.route("/api/firelink/cluster/top_nodes")
def cluster_top_nodes():
    """Get top nodes in the cluster"""
    return PrometheusClusterMetrics().cluster_info()


@app.route("/api/firelink/cluster/cpu_usage")
def cluster_cpu_usage():
    """Get CPU usage for the cluster"""
    return PrometheusClusterMetrics().cluster_cpu_usage()


@app.route("/api/firelink/cluster/memory_usage")
def cluster_memory_usage():
    """Get memory usage for the cluster"""
    return PrometheusClusterMetrics().cluster_memory_usage()


@app.route("/api/firelink/namespace/list")
def namespaces_list():
    """Get list of namespaces"""
    return Namespace(jsonify).list()


@app.route("/api/firelink/get_template", methods=["POST"])
def get_template():
    """Get template for an app"""
    return Apps(emit, jsonify).get_processed_template(request.json)


@app.route("/api/firelink/namespace/resource_metrics")
def namespace_resource_metrics():
    """Get resources for all namespaces"""
    namespaces = Namespace().list()
    namespaces = [
        namespace["namespace"] for namespace in namespaces if namespace["reserved"]
    ]
    metrics = PrometheusNamespaceMetrics().get_resources_for_namespaces(namespaces)
    return metrics


@app.route("/api/firelink/namespace/resource_metrics/<namespace>")
def namespace_resource_metrics_single(namespace):
    """Get resources for a single namespace"""
    return PrometheusNamespaceMetrics().get_resources_for_namespace(namespace)


@app.route("/api/firelink/namespace/top_pods", methods=["POST"])
def namespace_top_pods():
    """Get top pods for a namespace"""
    return PrometheusPodMetrics().top_pods(request.json["namespace"])


@app.route("/api/firelink/namespace/reserve", methods=["POST"])
def namespace_reserve():
    """Reserve a namespace"""
    return Namespace(jsonify).reserve(request.json, requester=identity_requester())


@app.route("/api/firelink/namespace/release", methods=["POST"])
def namespace_release():
    """Release a namespace"""
    return Namespace(jsonify).release(request.json, requester=identity_requester())


@app.route("/api/firelink/namespace/describe/<namespace>")
def namespace_describe(namespace):
    """Describe a namespace"""
    return Namespace(jsonify).describe(namespace)


@app.route("/api/firelink/apps/list")
def apps_list():
    """List apps"""
    return Apps(emit, jsonify).list()


@socketio.on("deploy-app")
def apps_deploy(incoming_request):
    """Deploy apps"""
    try:
        emit(
            "monitor-deploy-app",
            {
                "message": "Starting deployment for apps: ".join(
                    incoming_request["app_names"]
                )
            },
        )
        Apps(emit, jsonify).deploy(incoming_request)
    except Exception as e:
        emit("error-deploy-app", {"message": f"Server error deploying apps: {str(e)}"})


if __name__ == "__main__":
    socketio.run(app, port=port)
