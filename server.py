from urllib import request
from flask import Flask, send_from_directory
from flask import request
from firelink import firekeeper
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import os

app = Flask(__name__, static_folder="webroot")
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=600)

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
    j = request
    emit('monitor-deploy-app', {'message':"Starting deployment for " + j["app_names"][0]})
    apps.deploy(j["app_names"],
        j["source"],
        j["get_dependencies"],
        j["optional_deps_method"],
        j["set_image_tag"],
        j["ref_env"],
        j["target_env"],
        j["set_template_ref"],
        j["set_parameter"],
        j["clowd_env"],
        j["local_config_path"],
        j["remove_resources"],
        j["no_remove_resources"],
        j["remove_dependencies"],
        j["no_remove_dependencies"],
        j["single_replicas"],
        j["namespace"],
        j["name"],
        j["requester"],
        j["duration"],
        j["timeout"],
        j["no_release_on_fail"],
        j["component_filter"],
        j["import_secrets"],
        j["secrets_dir"],
        j["local"],
        j["frontends"],
        j["pool"])
    
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    if path == "":
        # Directly return index.html for the root URL
        return send_from_directory(app.static_folder, 'index.html')

    # Check if the file exists in the static directory
    static_path = os.path.join(app.static_folder, path)
    if os.path.exists(static_path):
        return send_from_directory(app.static_folder, path)

    # Fallback to 'index.html' if the file is not found
    return send_from_directory(app.static_folder, 'index.html')

app.before_request_funcs = [(None, firekeeper.login_to_openshift())]

CORS(app)

if __name__ == '__main__':
    socketio.run(app)




