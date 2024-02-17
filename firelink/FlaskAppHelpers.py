import subprocess
import os
from bonfire import qontract

class FlaskAppHelpers:
    # We verify health by ensuring we can talk to openshift
    def health(self):
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

    def login_to_openshift(self):
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

    def create_gql_client(self):
        global _client 
        try:
            _client = qontract.get_client()
            return
        except Exception as e:
            print("Failed to create gql client:", e)
            _client = None