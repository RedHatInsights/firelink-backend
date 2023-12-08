import operator
import time
import subprocess
import os
from bonfire import bonfire
from flask import jsonify
import json
from flask_socketio import emit

def health():
    try:
        subprocess.run(
            ["oc", "whoami"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return True
    except subprocess.CalledProcessError as e:
        return False

def login_to_openshift():
    oc_token = os.environ.get('OC_TOKEN')
    oc_server = os.environ.get('OC_SERVER')
    if oc_token and oc_server:
        try:
            result = subprocess.run(
                ["oc", "login", oc_server, "--token", oc_token],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            print(result.stdout)
        except subprocess.CalledProcessError as e:
            print("Failed to login:", e.stderr)
    else:
        print("OC_TOKEN and OC_SERVER env vars not found. Assuming local kubecontext.")

def containsVowels(string):
    string = string.lower()
    for char in string:
        if char in "aeiouAEIOU":
           return True
    return False

def route_guard():
    if not bonfire.has_ns_operator():
        bonfire._error(bonfire.NO_RESERVATION_SYS)

class Apps:
    def list(self, 
        source="appsre", 
        local_config_path="", 
        target_env="insights-ephemeral", 
        list_components=True):
        route_guard()

        apps = bonfire._get_apps_config(source, target_env, None, local_config_path)

        appsArray = []
        for app_name, app_dict in apps.items():
            #This is why people hate python BTW
            friendly_name  = " ".join([x.capitalize() if len(x) > 4 and containsVowels(x)  else x.upper() for x in app_name.split("-")])
            appsArray.append({"name": app_name, "friendly_name": friendly_name, "components": app_dict["components"]})
        
        appsArray.sort(key=operator.itemgetter('name'))

        return jsonify(appsArray)

    def deploy(self,
        app_names,
        source,
        get_dependencies,
        optional_deps_method,
        set_image_tag,
        ref_env,
        target_env,
        set_template_ref,
        set_parameter,
        clowd_env,
        local_config_path,
        remove_resources,
        no_remove_resources,
        remove_dependencies,
        no_remove_dependencies,
        single_replicas,
        namespace,
        name,
        requester,
        duration,
        timeout,
        no_release_on_fail,
        component_filter,
        import_secrets,
        secrets_dir,
        local,
        frontends,
        pool,
    ):
        DEPLOY_ERROR = 'error-deploy-app'
        DEPLOY_MONITOR = 'monitor-deploy-app'
        END_EVENT = 'end-deploy-app'

        try:
            route_guard()
        except Exception as e:
            emit(DEPLOY_ERROR, {'message': "Clowd Environment not found in deployment target"})
            return

        ns, reserved_new_ns = bonfire._get_namespace(namespace, name, requester, duration, pool, timeout, local)

        if import_secrets:
            bonfire.import_secrets_from_dir(secrets_dir)

        if not clowd_env:
            # if no ClowdEnvironment name provided, see if a ClowdEnvironment is associated with this ns
            match = bonfire.find_clowd_env_for_ns(ns)
            if not match:
                emit(DEPLOY_ERROR, {'message': f"Could not find a ClowdEnvironment tied to ns '{ns}'.  Specify which one "
                    "if you have already deployed one with '--clowd-env' or deploy one with "
                    "'bonfire deploy-env'"
                })
                return

            clowd_env = match["metadata"]["name"]
            #log.debug("inferred clowd_env: '%s'", clowd_env)

        def _err_handler(err):
            try:
                if not no_release_on_fail and reserved_new_ns:
                    # if we auto-reserved this ns, auto-release it on failure unless
                    # --no-release-on-fail was requested
                    emit(DEPLOY_MONITOR, {'message':"Releasing namespace " + ns})
                    bonfire.release_reservation(namespace=ns)
            finally:
                msg = "Deploy failed :("
                if str(err):
                    msg += f": {str(err)}"
                emit(DEPLOY_ERROR, {'message': msg})
            emit(END_EVENT, {'message: error': str(err)})

        try:
            emit(DEPLOY_MONITOR, {'message':"Processing app templates..."})
            apps_config = bonfire._process(
                app_names,
                source,
                get_dependencies,
                optional_deps_method,
                set_image_tag,
                ref_env,
                target_env,
                set_template_ref,
                set_parameter,
                clowd_env,
                local_config_path,
                remove_resources,
                no_remove_resources,
                remove_dependencies,
                no_remove_dependencies,
                single_replicas,
                component_filter,
                local,
                frontends,
            )
            #log.debug("app configs:\n%s", json.dumps(apps_config, indent=2))
            if not apps_config["items"]:
                emit(DEPLOY_MONITOR, {'message':"No configurations found to apply!"})
            else:
                emit(DEPLOY_MONITOR, {'message':"Applying app configs..."})
                bonfire.apply_config(ns, apps_config)
                emit(DEPLOY_MONITOR, {'message':"Waiting on resources for max of seconds: " + str(timeout)})
                bonfire._wait_on_namespace_resources(ns, timeout)
                emit(DEPLOY_MONITOR, {'message':"Deployment complete!"})
                emit(END_EVENT, {'message':"Deployment complete!"})
        except bonfire.TimedOutError as err:
            emit(DEPLOY_MONITOR, {'message':"Hit timeout error"})
            _err_handler(err)
        except bonfire.FatalError as err:
            emit(DEPLOY_MONITOR, {'message':"Hit fatal error"})
            _err_handler(err)
        except Exception as err:
            emit(DEPLOY_MONITOR, {'message':"Hit unexpected error"})
            _err_handler(err)
        else:
            emit(DEPLOY_MONITOR, {'message':"Successfully deployed to namespace " + ns})
            emit(END_EVENT)

class Namespace:
    DEFAULT_POOL_TYPE = "default"
    DEFAULT_DURATION = "1h"
    DEFAULT_TIMEOUT = 600
    DEFAULT_LOCAL = True

    def list(self):
        route_guard()
        namespaces = bonfire.get_namespaces(False, False)
        response = []
        for ns in namespaces:
            clowdApps = ns.clowdapps
            response.append({
                "namespace": ns.name,
                "reserved": ns.reserved,
                "status": ns.status,
                "requester": ns.requester,
                "expires_in": ns.expires_in,
                "pool_type": ns.pool_type,
                "clowdapps": clowdApps,
            })
        return jsonify(response)


    def reserve(self, opts):
        route_guard()

        requester = opts["requester"] if "requester" in opts else bonfire.get_requester()
        res_name = opts["name"] if "name" in opts else None
        duration = opts["duration"] if "duration" in opts else self.DEFAULT_DURATION
        pool_type = opts["pool_type"] if "pool_type" in opts else self.DEFAULT_POOL_TYPE
        timeout = opts["timeout"] if "timeout" in opts else self.DEFAULT_TIMEOUT
        local = opts["local"] if "local" in opts else self.DEFAULT_LOCAL

        if bonfire.check_for_existing_reservation(requester):
            response = {"namespace": "", "completed": False, "message": "You already have a reservation."}
        else:
            try:
                ns = bonfire.reserve_namespace(res_name, requester, duration, pool_type, timeout, local)
                response = {"namespace": ns.name, "completed": True, "message": "Namespace reserved"}
            except Exception as e:
                response = {"namespace": "", "completed": False, "message": str(e)}
        
        return jsonify(response)

    def release(self, opts):
        route_guard()

        #requester = opts["requester"] if "requester" in opts else bonfire.get_requester()
        local = opts["local"] if "local" in opts else self.DEFAULT_LOCAL

        nn = opts["namespace"] if "namespace" in opts else None
        if nn == None:
            response = {"completed": False, "message": "No namespace specified"}
        else:
            try:
                bonfire.release_reservation(None, nn, local)
                for attempt in range(5):
                    time.sleep(1)
                    released_namespace = bonfire.get_reservation(None, nn, None)
                    response = {"completed": False, "message": "Something went wrong verifying the release"}
                    if released_namespace  == None:
                        response = {"completed": True, "message": "Namespace released"}
                        break
            except Exception as e:
                response = {"completed": False, "message": str(e)}

        return jsonify(response)

    def describe(self, namespace):
        route_guard()
        try:
            descriptionText = bonfire.describe_namespace(namespace)
            response = {"completed": True, "message": descriptionText}
        except Exception as e:
            response = {"completed": False, "message": "ERROR: " + str(e)}
        return jsonify(response)