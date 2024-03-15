from bonfire import bonfire
from bonfire.utils import AppOrComponentSelector
from bonfire.elastic_logging import ElasticLogger
from firelink.AdaptorClassHelpers import AdaptorClassHelpers
import json
import os 

def dummy_emit(event, data):
    pass

class Apps:
    DEPLOY_ERROR_EVENT = 'error-deploy-app'
    DEPLOY_MONITOR_EVENT = 'monitor-deploy-app'
    DEPLOY_END_EVENT = 'end-deploy-app'
    DEPLOY_ERROR_EVENT = 'error-deploy-app'
    

    def __init__(self, emit=dummy_emit, jsonify=json.dumps):
        self.elastic_logger = ElasticLogger()
        self.helpers = AdaptorClassHelpers()
        self.jsonify = jsonify
        self.emit = emit

    def _log_to_elastic(self, message="successful deployment", success=True):
        telemetry_enabled = os.environ.get('ENABLE_TELEMETRY', 'False').lower() == 'true'
        if telemetry_enabled:
            self.elastic_logger.send_telemetry(message, success)

    def _app_name_contains_vowels(self, string):
        string = string.lower()
        for char in string:
            if char in "aeiouAEIOU":
                return True
        return False

    def _process_bonfire_apps_list(self, apps):
        appsArray = [
            {
                "name": app_name,
                "friendly_name": " ".join([x.capitalize() if len(x) > 4 and self._app_name_contains_vowels(x) else x.upper() for x in app_name.split("-")]),
                "components": app_dict["components"]
            }
            for app_name, app_dict in apps.items()
        ]
        appsArray.sort(key=lambda app: app['name'])
        return appsArray

    # TODO: There's no error handling here at all
    def list(self, 
        source="appsre", 
        local_config_path="", 
        target_env="insights-ephemeral",
        ref_env="insights-stage",
        fallback_ref_env="insights-stage",
        preferred_params={},
    ):
        self.helpers.route_guard()
        apps = bonfire._get_apps_config(source, target_env, ref_env, fallback_ref_env, None, None, preferred_params)
        appsArray = self._process_bonfire_apps_list(apps)
        return self.jsonify(appsArray)

    def _deploy_error_handler(self, err, request, ns, reserved_new_ns):
        try:
            if not request["no_release_on_fail"] and reserved_new_ns:
                self.emit(self.DEPLOY_MONITOR_EVENT, {'message':"Releasing namespace " + ns, 'completed': False, 'error': False})
                bonfire.release_reservation(namespace=ns)
        except Exception as e:
            self.emit(self.DEPLOY_ERROR_EVENT, {'message': f"Failed to release namespace {ns}: {str(e)}", 'completed': False, 'error': True})
        
        self._log_to_elastic(f"deployment failed: {str(err)}", success=False)
        self.emit(self.DEPLOY_END_EVENT, {'message' : 'Deployment Failed: ' + str(err), 'completed': False, 'error': True})

    def _get_clowdenv_for_ns(self, ns):
        cloud_env_reponse = bonfire.find_clowd_env_for_ns(ns)
        return cloud_env_reponse["metadata"]["name"] if cloud_env_reponse else None

    def _process_apps(self, request, ns, reserved_new_ns):
        # TODO: Send up a PR to bonfire to make a public method that accepts a dict
        apps_config = bonfire._process(
            request["app_names"],
            request["source"],
            request["get_dependencies"],
            request["optional_deps_method"],
            request["local_config_method"],
            request["set_image_tag"],
            request["ref_env"],
            request["fallback_ref_env"],
            request["target_env"],
            request["set_template_ref"],
            request["set_parameter"],
            request["clowd_env"],
            request["local_config_path"],
            AppOrComponentSelector(True, request["remove_resources"], []),
            AppOrComponentSelector(False, request["no_remove_resources"], []),
            AppOrComponentSelector(False, [], request["remove_dependencies"]),
            AppOrComponentSelector(True, [], request["no_remove_dependencies"]),
            request["single_replicas"],
            request["component_filter"],
            request["local"],
            request["frontends"],
            request["preferred_params"],
        )

        if not apps_config["items"]:
            self.emit(self.DEPLOY_MONITOR_EVENT, {'message':"No configurations found to apply!", 'completed': False, 'error': True})
            raise bonfire.FatalError("No configurations found to apply!")
        
        self.emit(self.DEPLOY_MONITOR_EVENT, {'message':"Applying app configs...", 'completed': False, 'error': False})
        bonfire.apply_config(ns, apps_config)
        #self.emit(self.DEPLOY_MONITOR_EVENT, {'message':"Waiting on resources for max of seconds: " + str(request["timeout"]) + ". This will continue in the background if you close this modal. ", 'completed': False, 'error': False})
        #bonfire._wait_on_namespace_resources(ns, request["timeout"])
        
        return apps_config

    def deploy(self, request):
        
        try:
            self.helpers.route_guard()
        except Exception as e:
            self.emit(self.DEPLOY_ERROR_EVENT, {'message': "Namespace Operator not detected on cluster", 'completed': False, 'error': True})
            return

        try:
            ns, reserved_new_ns = bonfire._get_namespace(request["namespace"], request["name"], request["requester"], request["duration"], request["pool"], request["timeout"], request["local"], True, True)
            self.emit(self.DEPLOY_MONITOR_EVENT, {'message': f"Using namespace {ns}", 'completed': False, 'namespace': ns, 'error': False})
        except Exception as e:
            self.emit(self.DEPLOY_ERROR_EVENT, {'message': f"Namespace failure: {str(e)}", 'completed': False, 'error': True})
            return
        
        if request["import_secrets"]:
            bonfire.import_secrets_from_dir(request["secrets_dir"])

        clowd_env = self._get_clowdenv_for_ns(ns)
        if not clowd_env:
            self.emit(self.DEPLOY_ERROR_EVENT, {'message': f"Could not find a ClowdEnvironment tied to ns '{ns}'.", 'completed': False, 'error': True})
            return
        request["clowd_env"] = clowd_env

        self.emit(self.DEPLOY_MONITOR_EVENT, {'message': "Processing app templates...", 'completed': False, 'error': False})

        try:
            self._process_apps(request, ns, reserved_new_ns)
        except (bonfire.TimedOutError, bonfire.FatalError, Exception) as err:
            self._deploy_error_handler(err, request, ns, reserved_new_ns)
            return
        else:
            self.emit(self.DEPLOY_END_EVENT, {'message': f"Deployed to {ns}. Resources may take additional time to become ready.", 'completed': True, 'error': False})
            self._log_to_elastic(f"successful deployment to {ns}", success=True)
