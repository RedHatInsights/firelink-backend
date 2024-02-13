from urllib import request
from flask import Flask, send_from_directory
from flask import request
from firelink import firekeeper
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import os
import logging

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=600, path="/api/firelink/socket.io")
port = int(os.getenv('PORT', 5000))  # Default to 5000 if not set

@app.route("/health")
def health():
    is_healthy = firekeeper.health()
    return ("", 200) if is_healthy else ("", 500)

@app.route("/api/firelink/namespace/list")
def namespaces_list():
    ns = firekeeper.Namespace()
    return ns.list()

@app.route("/api/firelink/namespace/reserve", methods=["POST"])
def namespace_reserve():
    ns = firekeeper.Namespace()
    return ns.reserve(request.json)

@app.route("/api/firelink/namespace/release", methods=["POST"])
def namespace_release():
    ns = firekeeper.Namespace()
    return ns.release(request.json)

@app.route("/api/firelink/namespace/describe/<namespace>")
def namespace_describe(namespace):
    ns = firekeeper.Namespace()
    return ns.describe(namespace)

@app.route("/api/firelink/apps/list")
def apps_list():
    apps = firekeeper.Apps()
    return apps.list()

@socketio.on('deploy-app')
def apps_deploy(request):
    apps = firekeeper.Apps()
    emit('monitor-deploy-app', {'message':"Starting deployment for " + request["app_names"][0]})
    print(request)
    apps.deploy(request["app_names"],
        request["source"],
        request["get_dependencies"],
        request["optional_deps_method"],
        request["set_image_tag"],
        request["ref_env"],
        request["target_env"],
        request["set_template_ref"],
        request["set_parameter"],
        request["clowd_env"],
        request["local_config_path"],
        request["remove_resources"],
        request["no_remove_resources"],
        request["remove_dependencies"],
        request["no_remove_dependencies"],
        request["single_replicas"],
        request["namespace"],
        request["name"],
        request["requester"],
        request["duration"],
        request["timeout"],
        request["no_release_on_fail"],
        request["component_filter"],
        request["import_secrets"],
        request["secrets_dir"],
        request["local"],
        request["frontends"],
        request["pool"])

@app.before_request
def log_request_info():
    app.logger.info(f"Request: {request.method} {request.url} - {request.remote_addr}")
    # If you want to log the request body as well, uncomment the following line
    # app.logger.info(f"Request Body: {request.get_data()}")


app.before_request_funcs = [(None, firekeeper.login_to_openshift(), firekeeper.create_gql_client())]

CORS(app)




if __name__ == '__main__':
    socketio.run(app, port=port)




