import sys
sys.path.append('.')
from firelink.Namespace import Namespace
import json
import time 

def test_namespace_list():
    namespaces = Namespace().list()
    assert len(namespaces) > 0

def test_namespace_reserve():
    ns_controller = Namespace()
    response = json.loads(ns_controller.reserve({"force": False, "pool": "default", "duration": "1h", "requester": "firelink-backend-tests"}))    
    assert response["completed"] == True
    ns_controller.release({"namespace": response["namespace"]})

def test_namespace_release():
    ns_controller = Namespace()
    namespace = json.loads(ns_controller.reserve({"force": False, "pool": "default", "duration": "1h", "requester": "firelink-backend-tests"}))  
    time.sleep(5)
    response = json.loads(ns_controller.release({"namespace": namespace["namespace"]}))
    assert response["completed"] == True

def test_namespace_release_no_name_specified():
    ns_controller = Namespace()
    response = json.loads(ns_controller.release({}))
    assert response["completed"] == False

def test_namespace_describe():
    ns_controller = Namespace()
    namespace = json.loads(ns_controller.reserve({"force": False, "pool": "default", "duration": "1h", "requester": "firelink-backend-tests"}))  
    response = json.loads(ns_controller.describe(namespace["namespace"]))
    assert response["completed"] == True
    ns_controller.release({"namespace": namespace["namespace"]})

