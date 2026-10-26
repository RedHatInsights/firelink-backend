"""Some helper functions for the adaptor classes"""
import threading

from bonfire import bonfire
from kubernetes import client as k8s_client
from kubernetes.client import ApiException


class AdaptorClassHelpers:
    """Helper functions for the adaptor classes"""

    NS_OPERATOR_CRD = ("cloud.redhat.com", "v1alpha1", "namespacereservations")

    def __init__(self, crd_client=None):
        self._crd_client = crd_client
        self._has_operator = None
        self._lock = threading.Lock()

    def _get_crd_client(self):
        if self._crd_client is None:
            self._crd_client = k8s_client.CustomObjectsApi()
        return self._crd_client

    def _check_ns_operator(self):
        group, version, plural = self.NS_OPERATOR_CRD
        try:
            self._get_crd_client().list_cluster_custom_object(
                group=group, version=version, plural=plural, limit=1
            )
            return True
        except ApiException as e:
            if e.status == 404:
                return False
            if e.status == 403:
                return True
            raise

    def _has_ns_operator(self):
        if self._has_operator is None:
            with self._lock:
                if self._has_operator is None:
                    self._has_operator = self._check_ns_operator()
        return self._has_operator

    def route_guard(self):
        """We run this before routes to ensure that the reservation system is available"""
        if not self._has_ns_operator():
            raise bonfire.FatalError(bonfire.NO_RESERVATION_SYS)
