import sys
sys.path.append('.')
from firelink.Apps import Apps
from firelink.Namespace import Namespace
import json

    

def test_apps_list():
    apps = Apps().list()
    assert len(apps) > 0

def test_apps_deploy():
    emit_response = {}
    namespace = None
    def dummy_emit(_, data):
        nonlocal emit_response 
        emit_response = data
        if 'namespace' in data:
            nonlocal namespace
            namespace = data['namespace']
    apps = Apps(emit=dummy_emit)
    apps.deploy({
        'app_names': ['rbac'], 
        'requester': 'firelink-backend-tests', 
        'duration': '10m', 
        'no_release_on_fail': False, 
        'frontends': False, 
        'pool': 'default', 
        'namespace': '', 
        'timeout': 600, 
        'source': 'appsre', 
        'get_dependencies': True, 
        'optional_deps_method': 'hybrid', 
        'set_image_tag': {}, 
        'ref_env': None, 
        'target_env': 'insights-ephemeral', 
        'local_config_method': 'merge',
        'set_template_ref': {}, 
        'set_parameter': {}, 
        'clowd_env': "", 
        'local_config_path': None, 
        'preferred_params': {},
        'fallback_ref_env': '',
        'remove_resources': [], 
        'no_remove_resources': [], 
        'remove_dependencies': [], 
        'no_remove_dependencies': [], 
        'single_replicas': True, 
        'name': None, 
        'component_filter': [], 
        'import_secrets': False, 
        'secrets_dir': '', 
        'local': True
    })
    assert emit_response['completed'] == True
    if namespace:
        Namespace().release({'namespace': namespace})




