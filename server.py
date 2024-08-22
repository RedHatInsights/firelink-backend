import logging
from urllib import request
from flask import Flask
from flask import request
from flask import jsonify
from firelink.Apps import Apps
from firelink.FlaskAppHelpers import FlaskAppHelpers
from firelink.Namespace import Namespace
from firelink.Metrics import PrometheusNamespaceMetrics, PrometheusPodMetrics
from firelink.Metrics import ClusterResourceMetrics
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import sys
import os
from flask_caching import Cache

DEFAULT_PORT = 5000

app = Flask(__name__)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=600, path="/api/firelink/socket.io")
port = int(os.getenv('PORT', DEFAULT_PORT))
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
    logging.info(f"Request: {request.method} {request.url} - {request.remote_addr}")

# This line has to come after before_request is defined or it freaks out
app.before_request_funcs = [(None, helpers.login_to_openshift(), helpers.create_gql_client())]

@app.route("/health")
def health():
    return ("", 200) if FlaskAppHelpers().health() else ("", 500)

@app.route("/api/firelink/cluster/top_pods")
def cluster_top_pods():
    return ClusterResourceMetrics().all_top_pods()

@app.route("/api/firelink/cluster/top_nodes")
def cluster_top_nodes():
    return ClusterResourceMetrics().top_nodes()

@app.route("/api/firelink/namespace/list")
def namespaces_list():
    return Namespace(jsonify).list()

# Get resources for all namespaces
@app.route("/api/firelink/namespace/resource_metrics")
@cache.cached(timeout=120)
def namespace_resource_metrics():
    namespaces = Namespace(lambda x:x).list()
    namespaces = [namespace["namespace"] for namespace in namespaces if namespace["reserved"]]
    metrics = PrometheusNamespaceMetrics().get_resources_for_namespaces(namespaces)
    return metrics

# Get resources for a single namespace
@app.route("/api/firelink/namespace/resource_metrics/<namespace>")
def namespace_resource_metrics_single(namespace):
    return PrometheusNamespaceMetrics().get_resources_for_namespace(namespace)

@app.route("/api/firelink/namespace/top_pods", methods=["POST"])
def namespace_top_pods():
    return PrometheusPodMetrics().top_pods(request.json["namespace"])

@app.route("/api/firelink/namespace/reserve", methods=["POST"])
def namespace_reserve():
    return Namespace(jsonify).reserve(request.json)

@app.route("/api/firelink/namespace/release", methods=["POST"])
def namespace_release():
    return Namespace(jsonify).release(request.json)

@app.route("/api/firelink/namespace/describe/<namespace>")
def namespace_describe(namespace):
    return Namespace(jsonify).describe(namespace)

@app.route("/api/firelink/apps/list")
def apps_list():
    return Apps(emit, jsonify).list()

@socketio.on('deploy-app')
def apps_deploy(request):
    try:
        emit('monitor-deploy-app', {'message':"Starting deployment for apps: ".join(request["app_names"])})
        Apps(emit, jsonify).deploy(request)
    except Exception as e:
        emit('error-deploy-app', {'message':f"Server error deploying apps: {str(e)}"})

if __name__ == '__main__':
    socketio.run(app, port=port)




