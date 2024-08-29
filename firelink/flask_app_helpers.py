"""Helper functions for the Flask app."""
import os
import subprocess
from bonfire import qontract

class FlaskAppHelpers:
    """Helper functions for the Flask app."""
    def health(self):
        """We check health by ensuring we can talk to the OpenShift API."""
        try:
            subprocess.run(
                ["oc", "whoami"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return True
        except subprocess.CalledProcessError as _e:
            return False

    def login_to_openshift(self):
        """Login to OpenShift using the OC_TOKEN and OC_SERVER env vars."""
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
        """Create a global GraphQL client."""
        global _client 
        try:
            _client = qontract.get_client()
            return
        except Exception as e:
            print("Failed to create gql client:", e)
            _client = None