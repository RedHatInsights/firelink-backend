import sys
sys.path.append('.')
from firelink.Apps import Apps
import json

    

def test_apps_list():
    apps = Apps().list()
    assert len(apps) > 0

def test_apps_deploy():
    emit_response = {}
    def dummy_emit(_, data):
        nonlocal emit_response 
        emit_response = data
    apps = Apps(emit=dummy_emit)
    apps.deploy({
        "app_names":["rbac"],
        "requester":"firelink-backend-test",
        "duration":"10m",
        "no_release_on_fail": False,
        "frontends": False,
        "pool":"default",
        "namespace":"",
        "timeout":600,
        "source":"appsre",
        "get_dependencies": True,
        "optional_deps_method":"hybrid",
        "set_image_tag":{},
        "ref_env": False,
        "target_env":"insights-ephemeral",
        "set_template_ref":{},
        "set_parameter":{},
        "clowd_env": "",
        "local_config_path": "",
        "remove_resources":[],
        "no_remove_resources":[],
        "remove_dependencies":[],
        "no_remove_dependencies":[],
        "single_replicas": True,
        "name":"",
        "component_filter":[],
        "import_secrets":False,
        "secrets_dir":"",
        "local":False
    })
    assert emit_response["completed"] == True



