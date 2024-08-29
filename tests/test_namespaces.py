"""Namespace tests"""
import sys
import json
import concurrent.futures
sys.path.append('.')
from firelink.openshift_resources import Namespace

def _reserve_namespace():
    ns_controller = Namespace()
    return ns_controller.reserve({
        "force": False, 
        "pool": "default", 
        "duration": "10m", 
        "requester": "firelink-backend-tests"})

# Depending on external factors this test can occasionally fail
# If the CRCD cluster doesn't have enough namespaces available or
# is too slow to release and create new ones this test will fail
# This isn't a problem with the code but with the cluster itself
# If this test and no other tests fail re-running this test should
# run and pass
class TestNamespaceConcurrency:
    """Test to ensure that namespace reservation is thread-safe"""

    def test_namespace_reserve_concurrency(self):
        """Test to ensure that namespace reservation is thread-safe"""
        print("test_namespace_reserve_concurrency")
        ns_controller = Namespace()
        num_threads = 4  # Number of concurrent threads
        results = []

        # Define the task for each thread
        def reserve_and_release():
            response = _reserve_namespace()
            assert response["completed"] is True
            print(f"Reserved namespace: {response['namespace']}")
            ns_controller.release({"namespace": response["namespace"]})
            return response["namespace"]

        # Use ThreadPoolExecutor to execute the tasks concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            future_to_namespace = {
                executor.submit(reserve_and_release): i for i in range(num_threads)
            }
            for future in concurrent.futures.as_completed(future_to_namespace):
                print(f"Future completed: {future}")
                namespace = future.result()
                results.append(namespace)

        # Check if all namespaces are unique (no duplicates)
        assert len(results) == len(set(results)), "Duplicate namespaces were reserved"


def test_namespace_list():
    """Test to ensure that namespace listing works"""
    namespaces = Namespace().list()
    assert len(namespaces) > 0

def test_namespace_reserve():
    """Test to ensure that namespace reservation works"""
    ns_controller = Namespace()
    response = _reserve_namespace()
    assert response["completed"] is True
    ns_controller.release({"namespace": response["namespace"]})

def test_namespace_release():
    """Test to ensure that namespace release works"""
    ns_controller = Namespace()
    namespace = _reserve_namespace()
    response = ns_controller.release({"namespace": namespace["namespace"]})
    assert response["completed"] is True

def test_namespace_release_no_name_specified():
    """Test to ensure that namespace release fails when no namespace is specified"""
    ns_controller = Namespace()
    response = ns_controller.release({})
    assert response["completed"] is False

def test_namespace_describe():
    """Test to ensure that namespace description works"""
    ns_controller = Namespace()
    namespace = _reserve_namespace()
    response = ns_controller.describe(namespace["namespace"])
    assert response["completed"] is True
    ns_controller.release({"namespace": namespace["namespace"]})

def test_namespace_reserve_already_exists():
    """Test to ensure that namespace reservation fails when a reservation already exists"""
    ns_controller = Namespace()
    namespace = _reserve_namespace() 
    response = ns_controller.reserve({
        "force": False, 
        "pool": "default", 
        "duration": "10m", 
        "requester": "firelink-backend-tests"}) 
    assert response["completed"] is False
    ns_controller.release({"namespace": namespace["namespace"]})
