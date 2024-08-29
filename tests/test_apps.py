import sys
sys.path.append('.')
from firelink.apps import Apps
from firelink.openshift_resources import Namespace
import json
import multiprocessing
import pytest

def worker(apps):
    return apps.list()

class TestAppsListConcurrency:
    @pytest.fixture(scope="class")

    def test_apps_list_concurrency(self):
        apps_instance = Apps()
        num_processes = 10  # Number of concurrent processes
        pool = multiprocessing.Pool(processes=num_processes)

        results = pool.map(worker, [apps_instance] * num_processes)

        # Check for consistency across all results
        reference_result = results[0]
        for result in results[1:]:
            assert result == reference_result, "Inconsistent results from concurrent execution"

        apps_list = reference_result
        assert len(apps_list) > 0, "Expected non-empty list of apps"

        pool.close()
        pool.join()

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




