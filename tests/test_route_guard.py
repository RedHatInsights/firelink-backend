"""Tests for AdaptorClassHelpers.route_guard"""
import sys

sys.path.append('.')
from unittest.mock import MagicMock

import pytest
from kubernetes.client import ApiException

from bonfire import bonfire
from firelink.adaptor_class_helpers import AdaptorClassHelpers


def _client(status=None):
    client = MagicMock()
    if status is None:
        client.list_cluster_custom_object.return_value = {"items": []}
    else:
        client.list_cluster_custom_object.side_effect = ApiException(status=status)
    return client


def test_operator_present_passes_guard():
    helpers = AdaptorClassHelpers(crd_client=_client())
    helpers.route_guard()


def test_operator_missing_raises_fatal_error():
    helpers = AdaptorClassHelpers(crd_client=_client(404))
    with pytest.raises(bonfire.FatalError, match=bonfire.NO_RESERVATION_SYS):
        helpers.route_guard()


def test_forbidden_crq_treated_as_present():
    helpers = AdaptorClassHelpers(crd_client=_client(403))
    helpers.route_guard()


def test_unexpected_error_propagates():
    helpers = AdaptorClassHelpers(crd_client=_client(500))
    with pytest.raises(ApiException):
        helpers.route_guard()


def test_check_result_is_cached():
    client = _client()
    helpers = AdaptorClassHelpers(crd_client=client)
    assert helpers._check_ns_operator() is True
    assert helpers._check_ns_operator() is True
    assert client.list_cluster_custom_object.call_count == 1


def test_queries_cluster_scoped_crd():
    client = _client()
    AdaptorClassHelpers(crd_client=client).route_guard()
    client.list_cluster_custom_object.assert_called_once_with(
        group="cloud.redhat.com",
        version="v1alpha1",
        plural="namespacereservations",
        limit=1,
    )
