from urllib import request
from flask import Flask
from flask import request
from flask import jsonify
from firelink.Apps import Apps
from firelink.Namespace import Namespace
from firelink.FlaskAppHelpers import FlaskAppHelpers
from firelink.Metrics import NamespaceResourceMetrics
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import os

DEFAULT_PORT = 5000

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=600, path="/api/firelink/socket.io")
port = int(os.getenv('PORT', DEFAULT_PORT))
helpers = FlaskAppHelpers()

CORS(app)

@app.before_request
def log_request_info():
    app.logger.info(f"Request: {request.method} {request.url} - {request.remote_addr}")
# This line has to come after before_request is defined or it freaks out
app.before_request_funcs = [(None, helpers.login_to_openshift(), helpers.create_gql_client())]

@app.route("/health")
def health():
    return ("", 200) if FlaskAppHelpers().health() else ("", 500)

@app.route("/api/firelink/namespace/list")
def namespaces_list():
    return Namespace(jsonify).list()

@app.route("/api/firelink/namespace/resource_metrics")
def namespace_resource_metrics():
    namespaces = Namespace(lambda x:x).list()
    namespaces = [namespace["namespace"] for namespace in namespaces if namespace["reserved"]]
    metrics = NamespaceResourceMetrics().get_resources_for_namespaces(namespaces)
    return metrics

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
    emit('monitor-deploy-app', {'message':"Starting deployment for apps: ".join(request["app_names"])})
    Apps(emit, jsonify).deploy(request)

if __name__ == '__main__':
    socketio.run(app, port=port)




