"""Unit test: namespace describe must not return cleartext credentials."""
import sys
sys.path.append('.')
from firelink.openshift_resources import Namespace


SAMPLE_DESCRIPTION = """\
namespace: ephemeral-abc123
requester: someone
keycloak_admin_route: https://keycloak-ephemeral-abc123.apps.example.com
keycloak_admin_login: admin | s3cr3t-admin-pw
gateway_route: https://front-end-ephemeral-abc123.apps.example.com
default_user_login: jdoe | s3cr3t-user-pw
3 ClowdApps deployed, 1 Frontends deployed
"""


def test_describe_redacts_credentials():
    """_parse_description_to_json must never echo the bonfire-provided
    Keycloak admin or gateway passwords back to API callers."""
    ns = Namespace.__new__(Namespace)  # bypass __init__ (no cluster needed)
    parsed = ns._parse_description_to_json(SAMPLE_DESCRIPTION)

    assert parsed['keycloak_admin']['login']['username'] == 'admin'
    assert parsed['gateway']['login']['username'] == 'jdoe'
    assert 's3cr3t-admin-pw' not in str(parsed)
    assert 's3cr3t-user-pw' not in str(parsed)
    assert parsed['keycloak_admin']['login']['password'] == '********'
    assert parsed['gateway']['login']['password'] == '********'
