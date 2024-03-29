import time
from bonfire import bonfire
from bonfire.utils import AppOrComponentSelector
from firelink.AdaptorClassHelpers import AdaptorClassHelpers
import json

class Namespace:
    DEFAULT_POOL_TYPE = "default"
    DEFAULT_DURATION = "1h"
    DEFAULT_TIMEOUT = 600
    DEFAULT_LOCAL = True
    DEFAULT_RELEASE_TRIES = 30
    DEFAULT_RELEASE_WAIT_SECONDS = 1

    def __init__(self, jsonify=json.dumps):
        self.helpers = AdaptorClassHelpers()
        self.jsonify = jsonify

    def _process_namespace_list(self, namespaces):
        return [
            {
                "namespace": ns.name,
                "reserved": ns.reserved,
                "status": ns.status,
                "requester": ns.requester,
                "expires_in": ns.expires_in,
                "pool_type": ns.pool_type,
                "clowdapps": ns.clowdapps,
            }
            for ns in namespaces
        ]

    def list(self):
        self.helpers.route_guard()
        namespaces = bonfire.get_namespaces(False, False)
        response = self._process_namespace_list(namespaces)
        return self.jsonify(response)

    def reserve(self, opts):
        self.helpers.route_guard()

        requester = opts.get("requester", bonfire._get_requester())
        res_name = opts.get("name")
        duration = opts.get("duration", self.DEFAULT_DURATION)
        pool_type = opts.get("pool_type", self.DEFAULT_POOL_TYPE)
        timeout = opts.get("timeout", self.DEFAULT_TIMEOUT)
        local = opts.get("local", self.DEFAULT_LOCAL)
        force = opts.get("force", False)

        if bonfire.check_for_existing_reservation(requester) and not force:
            response = {"namespace": "", "completed": False, "message": "You already have a reservation."}
            return self.jsonify(response)
        
        try:
            ns = bonfire.reserve_namespace(res_name, requester, duration, pool_type, timeout, local)
            response = {"namespace": ns.name, "completed": True, "message": "Namespace reserved"}
        except Exception as e:
            response = {"namespace": "", "completed": False, "message": str(e)}
        
        return self.jsonify(response)

    def _try_relase_loop(self, namespace):
        for _ in range(self.DEFAULT_RELEASE_TRIES):
            time.sleep(self.DEFAULT_RELEASE_WAIT_SECONDS)
            released_namespace = bonfire.get_reservation(None, namespace, None)
            response = {"completed": False, "message": "Something went wrong verifying the release"}
            if released_namespace  == None:
                response = {"completed": True, "message": "Namespace released"}
                break
        return response

    def release(self, opts):
        self.helpers.route_guard()

        namespace = opts.get("namespace")
        if not namespace:
            response = {"completed": False, "message": "No namespace specified"}
            return self.jsonify(response)

        try:
            bonfire.release_reservation(None, namespace, opts.get("local", self.DEFAULT_LOCAL))
            response = self._try_relase_loop(namespace)
        except Exception as e:
            response = {"completed": False, "message": str(e)}

        return self.jsonify(response)

    def describe(self, namespace):
        self.helpers.route_guard()
        try:
            descriptionText = bonfire.describe_namespace(namespace, "string")
            response = {"completed": True, "message": self. _parse_description_to_json(descriptionText)}
        except Exception as e:
            response = {"completed": False, "message": "ERROR: " + str(e)}
        return self.jsonify(response)

    def _parse_description_to_json(self, description_text):
        lines = description_text.strip().split('\n')
        result = {}
        keycloak_admin = {}
        gateway = {}

        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower().replace(' ', '_')
                value = value.strip()

                if 'keycloak_admin_route' in key:
                    keycloak_admin['route'] = value
                elif 'keycloak_admin_login' in key:
                    username, password = value.split(' | ')
                    keycloak_admin['login'] = {'username': username, 'password': password}
                elif 'gateway_route' in key:
                    gateway['route'] = value
                elif 'default_user_login' in key:
                    username, password = value.split(' | ')
                    gateway['login'] = {'username': username, 'password': password}
                else:
                    result[key] = value
            elif 'deployed' in line:
                clowdapps, frontends = line.split(',')
                result['clowdapps_deployed'] = int(clowdapps.split()[0])
                result['frontends_deployed'] = int(frontends.split()[0])

        if keycloak_admin:
            result['keycloak_admin'] = keycloak_admin
        if gateway:
            result['gateway'] = gateway

        return result

