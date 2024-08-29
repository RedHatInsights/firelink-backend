import sys
sys.path.append('.')
from firelink.openshift_resources import Namespace
import json
import concurrent.futures

def _reserve_namespace():
    ns_controller = Namespace()
    response = json.loads(ns_controller.reserve({"force": False, "pool": "default", "duration": "10m", "requester": "firelink-backend-tests"}))    
    return response

class TestNamespaceConcurrency:
    def test_namespace_reserve_concurrency(self):
        print("test_namespace_reserve_concurrency")
        ns_controller = Namespace()
        num_threads = 4  # Number of concurrent threads
        results = []

        # Define the task for each thread
        def reserve_and_release():
            response = _reserve_namespace()
            assert response["completed"] == True
            print(f"Reserved namespace: {response['namespace']}")
            ns_controller.release({"namespace": response["namespace"]})
            return response["namespace"]

        # Use ThreadPoolExecutor to execute the tasks concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            future_to_namespace = {executor.submit(reserve_and_release): i for i in range(num_threads)}
            for future in concurrent.futures.as_completed(future_to_namespace):
                print(f"Future completed: {future}")
                namespace = future.result()
                results.append(namespace)

        # Check if all namespaces are unique (no duplicates)
        assert len(results) == len(set(results)), "Duplicate namespaces were reserved"


def test_namespace_list():
    namespaces = Namespace().list()
    assert len(namespaces) > 0

def test_namespace_reserve():
    ns_controller = Namespace()
    response = _reserve_namespace()    
    assert response["completed"] == True
    ns_controller.release({"namespace": response["namespace"]})

def test_namespace_release():
    ns_controller = Namespace()
    namespace = _reserve_namespace() 
    response = json.loads(ns_controller.release({"namespace": namespace["namespace"]}))
    assert response["completed"] == True

def test_namespace_release_no_name_specified():
    ns_controller = Namespace()
    response = json.loads(ns_controller.release({}))
    assert response["completed"] == False

def test_namespace_describe():
    ns_controller = Namespace()
    namespace = _reserve_namespace() 
    response = json.loads(ns_controller.describe(namespace["namespace"]))
    assert response["completed"] == True
    ns_controller.release({"namespace": namespace["namespace"]})

def test_namespace_reserve_already_exists():
    ns_controller = Namespace()
    namespace = _reserve_namespace() 
    response = json.loads(ns_controller.reserve({"force": False, "pool": "default", "duration": "10m", "requester": "firelink-backend-tests"}))    
    assert response["completed"] == False
    ns_controller.release({"namespace": namespace["namespace"]})

