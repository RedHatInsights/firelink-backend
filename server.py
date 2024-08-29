"""Flask API server for Firelink"""
import logging
import sys
import os
from flask import Flask
from flask import request
from flask import jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from flask_caching import Cache
from firelink.apps import Apps
from firelink.flask_app_helpers import FlaskAppHelpers
from firelink.openshift_resources import Namespace
from firelink.metrics import (PrometheusNamespaceMetrics,
PrometheusPodMetrics,
PrometheusClusterMetrics)

DEFAULT_PORT = 5000

app = Flask(__name__)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=600, path="/api/firelink/socket.io")
port = int(os.getenv('PORT', str(DEFAULT_PORT)))
helpers = FlaskAppHelpers()

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

CORS(app)

@app.before_request
def log_request_info():
    """Log request information"""
    logging.info("Request: %s %s - %s", request.method, request.url, request.remote_addr)

# This line has to come after before_request is defined or it freaks out
app.before_request_funcs = [(None, helpers.login_to_openshift(), helpers.create_gql_client())]

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

# Get resources for all namespaces
@app.route("/api/firelink/namespace/resource_metrics")
def namespace_resource_metrics():
    """Get resources for all namespaces"""
    namespaces = Namespace().list()
    namespaces = [namespace["namespace"] for namespace in namespaces if namespace["reserved"]]
    metrics = PrometheusNamespaceMetrics().get_resources_for_namespaces(namespaces)
    return metrics

# Get resources for a single namespace
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
    return Namespace(jsonify).reserve(request.json)

@app.route("/api/firelink/namespace/release", methods=["POST"])
def namespace_release():
    """Release a namespace"""
    return Namespace(jsonify).release(request.json)

@app.route("/api/firelink/namespace/describe/<namespace>")
def namespace_describe(namespace):
    """Describe a namespace"""
    return Namespace(jsonify).describe(namespace)

@app.route("/api/firelink/apps/list")
def apps_list():
    """List apps"""
    return Apps(emit, jsonify).list()

@socketio.on('deploy-app')
def apps_deploy(incoming_request):
    """Deploy apps"""
    try:
        emit('monitor-deploy-app', {'message':"Starting deployment for apps: ".join(incoming_request["app_names"])})
        Apps(emit, jsonify).deploy(incoming_request)
    except Exception as e:
        emit('error-deploy-app', {'message':f"Server error deploying apps: {str(e)}"})

if __name__ == '__main__':
    socketio.run(app, port=port)
