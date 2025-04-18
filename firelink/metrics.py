"""Module to handle Prometheus queries for cluster, pod, and namespace metrics."""
import os
import warnings
from prometheus_api_client import PrometheusConnect
from urllib3.exceptions import InsecureRequestWarning
import urllib3

# Suppress only the specific InsecureRequestWarning from urllib3
warnings.simplefilter('ignore', InsecureRequestWarning)
# Disable all urllib3 warnings
urllib3.disable_warnings(InsecureRequestWarning)

class ClusterQueries:
    """Class to hold Prometheus queries for cluster metrics."""
    def cluster_cpu_usage(self):
        """Query to get the cluster CPU usage."""
        return 'cluster:node_cpu:ratio_rate5m{cluster=""}'

    def cluster_memory_usage(self):
        """Query to get the cluster memory usage."""
        return 'cluster:memory_usage:ratio{cluster=""}'

    def namespace_cpu_usage(self):
        """Query to get the namespace CPU usage."""
        return "sum(node_namespace_pod_container:container_cpu_usage_seconds_total:sum_irate{cluster=""}) by (namespace)"

    def node_capacity(self):
        """Query to get the node capacity."""
        return 'kube_node_status_capacity'

    def node_allocatable(self):
        """Query to get the node allocatable."""
        return 'kube_node_status_allocatable'

class PodQueries:
    """Class to hold Prometheus queries for pod metrics."""
    def pod_cpu_usage(self, namespace):
        """Query to get the pod CPU usage."""
        return f'sum(node_namespace_pod_container:container_cpu_usage_seconds_total:sum_irate{{cluster="", namespace="{namespace}"}}) by (pod)'

    def pod_memory_usage(self, namespace):
        """Query to get the pod memory usage."""
        return f'sum(container_memory_working_set_bytes{{namespace="{namespace}"}}) by (pod)'

class MemoryQueries:
    """Class to hold Prometheus queries for memory metrics."""
    def limits(self, namespaces):
        return f'sum by (namespace) (kube_pod_resource_limit{{resource="memory", namespace=~"{namespaces}"}})'

    def requests(self, namespaces):
        return f'sum by (namespace) (kube_pod_resource_request{{resource="memory", namespace=~"{namespaces}"}})'

    def usage(self, namespaces):
        return f'sum(container_memory_working_set_bytes{{namespace=~"{namespaces}",container="",pod!=""}}) BY (namespace)'

class CPUQueries:
    """Class to hold Prometheus queries for CPU metrics."""
    def limits(self, namespaces):
        return f'sum by (namespace) (kube_pod_resource_limit{{resource="cpu", namespace=~"{namespaces}"}})'

    def requests(self, namespaces):
        return f'sum by (namespace) (kube_pod_resource_request{{resource="cpu", namespace=~"{namespaces}"}})'

    def usage(self, namespaces):
        return f'sum(rate(container_cpu_usage_seconds_total{{namespace=~"{namespaces}",container!="POD"}}[5m])) by (namespace)'

class PrometheusClusterMetrics:
    """Class to handle Prometheus queries for cluster metrics."""
    def __init__(self):
        prometheus_url = os.getenv("PROMETHEUS_URL")
        bearer_token = os.getenv("OC_TOKEN")
        self.prometheus_api = PrometheusConnect(
            url=prometheus_url,
            headers={"Authorization": f"Bearer {bearer_token}"},
            disable_ssl=True
        )

    def cluster_cpu_usage(self):
        """Get the cluster CPU usage."""
        query = ClusterQueries().cluster_cpu_usage()
        try:
            results = self.prometheus_api.custom_query(query=query)
            return self._format_result(results)
        except Exception as e:
            print(f"Error running query: {e}")
            return None
 
    def cluster_memory_usage(self):
        """Get the cluster memory usage."""
        query = ClusterQueries().cluster_memory_usage()
        try:
            results = self.prometheus_api.custom_query(query=query)
            return self._format_result(results)
        except Exception as e:
            print(f"Error running query: {e}")
            return None

    def cluster_info(self):
        """Get the cluster info."""
        results = []
        results = self._process_node_metrics(self._cluster_node_capacity(), "capacity", results)
        results = self._process_node_metrics(self._cluster_node_allocatable(), "allocatable", results)
        results = self._add_usage_metrics(results)
        return results

    def _add_usage_metrics(self, nodes):
        for node in nodes:
            for resource, resource_metrics in node.items():
                if resource == "node":
                    continue  # Skip the node name entry
                    
                capacity = None
                allocatable = None

                # Extract capacity and allocatable values
                for metric in resource_metrics:
                    if metric['type'] == 'capacity':
                        capacity = float(metric['value'])
                    elif metric['type'] == 'allocatable':
                        allocatable = float(metric['value'])

                if capacity is not None and allocatable is not None:
                    # Calculate usage and usage_percent
                    usage = capacity - allocatable
                    usage_percent = (usage / capacity) * 100 if capacity > 0 else 0

                    # Add the new metrics to the list
                    resource_metrics.append({"type": "usage", "unit": "byte", "value": str(usage)})
                    resource_metrics.append({"type": "usage_percent", "unit": "float", "value": str(usage_percent)})
        
        return nodes

    def _add_metric_to_results(self, results, node_name, resource, metric_data):
        for result in results:
            if result["node"] == node_name:
                if resource in result:
                    result[resource].append(metric_data)
                else:
                    result[resource] = [metric_data]
                return
        results.append({"node": node_name, resource: [metric_data]})

    def _process_node_metrics(self, prom_results, metric_type, results=None):
        if results is None:
            results = []
        for prom_result in prom_results:
            metric = prom_result["metric"]
            value = prom_result["value"][1]
            node_name = metric["node"]
            metric_data = {"type": metric_type, "value": value, "unit": metric["unit"]}
            self._add_metric_to_results(results, node_name, metric["resource"], metric_data)
        return results

    def _cluster_node_capacity(self):
        query = ClusterQueries().node_capacity()
        try:
            results = self.prometheus_api.custom_query(query=query)
            return results
        except Exception as e:
            print(f"Error running query: {e}")
            return None
    
    def _cluster_node_allocatable(self):
        query = ClusterQueries().node_allocatable()
        try:
            results = self.prometheus_api.custom_query(query=query)
            return results
        except Exception as e:
            print(f"Error running query: {e}")
            return None

    def _format_result(self, result):
        usage = float(result[0]["value"][1])
        return {"value": usage}

class PrometheusPodMetrics:
    """Class to handle Prometheus queries for pod metrics."""
    
    def __init__(self):
        prometheus_url = os.getenv("PROMETHEUS_URL")
        bearer_token = os.getenv("OC_TOKEN")
        self.prometheus_api = PrometheusConnect(
            url=prometheus_url,
            headers={"Authorization": f"Bearer {bearer_token}"},
            disable_ssl=True
        )

    def top_pods(self, namespace):
        """Get the top pods for a namespace by CPU and memory usage."""
        cpu_results = self._top_pods_cpu(namespace)
        memory_results = self._top_pods_memory(namespace)
        if cpu_results is None or memory_results is None:
            return None
        results = []
        for cpu_result in cpu_results:
            result = {
                "name": cpu_result["metric"]["pod"],
                "cpu": float(cpu_result["value"][1]),
            }
            for memory_result in memory_results:
                if memory_result["metric"]["pod"] == cpu_result["metric"]["pod"]:
                    result["ram"] = float(memory_result["value"][1]) / (1024**3)
                    break
            results.append(result)
        return results

    def _top_pods_cpu(self, namespace):
        query = PodQueries().pod_cpu_usage(namespace)
        try:
            results = self.prometheus_api.custom_query(query=query)
            return results
        except Exception as e:
            print(f"Error running query: {e}")
            return None
    
    def _top_pods_memory(self, namespace):
        query = PodQueries().pod_memory_usage(namespace)
        try:
            results = self.prometheus_api.custom_query(query=query)
            return results
        except Exception as e:
            print(f"Error running query: {e}")
            return None
            
class PrometheusNamespaceMetrics:
    """Class to handle Prometheus queries for namespace metrics."""

    def __init__(self):
        prometheus_url = os.getenv("PROMETHEUS_URL")
        bearer_token = os.getenv("OC_TOKEN")
        self.prometheus_api = PrometheusConnect(url=prometheus_url,headers={"Authorization": f"Bearer {bearer_token}"},disable_ssl=True)

    def _run_query(self, query):
        """Run a Prometheus query and return the results."""
        try:
            results = self.prometheus_api.custom_query(query=query)
            return results
        except Exception as e:
            print(f"Error running query: {e}")
            return None

    def get_resources_for_namespace(self, namespace):
        """Get resources for a single namespace."""
        # Generate batched queries
        cpu_limits = self._run_query(CPUQueries().limits(namespace))
        cpu_requests = self._run_query(CPUQueries().requests(namespace))
        cpu_usage = self._run_query(CPUQueries().usage(namespace)) 
        memory_limits = self._run_query(MemoryQueries().limits(namespace))
        memory_requests = self._run_query(MemoryQueries().requests(namespace))
        memory_usage = self._run_query(MemoryQueries().usage(namespace))

        # Process the results
        resources = {
            'limits': {
                'cpu': self._extract_cpu_value(cpu_limits, namespace), 
                'memory': self._extract_memory_value(memory_limits, namespace)
            },
            'requests': {
                'cpu': self._extract_cpu_value(cpu_requests, namespace),
                'memory': self._extract_memory_value(memory_requests, namespace)
            },
            'usage': {
                'cpu': self._extract_cpu_value(cpu_usage, namespace),
                'memory': self._extract_memory_value(memory_usage, namespace)
            }
        }

        return resources

    def get_resources_for_namespaces(self, namespaces):
        """Get resources for a list of namespaces."""
        # Create a regex pattern to match all the namespaces
        namespace_pattern = "|".join(namespaces)

        # Generate batched queries
        cpu_limits = self._run_query(CPUQueries().limits(namespace_pattern))
        cpu_requests = self._run_query(CPUQueries().requests(namespace_pattern))
        cpu_usage = self._run_query(CPUQueries().usage(namespace_pattern))
        memory_limits = self._run_query(MemoryQueries().limits(namespace_pattern))
        memory_requests = self._run_query(MemoryQueries().requests(namespace_pattern))
        memory_usage = self._run_query(MemoryQueries().usage(namespace_pattern))

        # Process the results and map them back to each namespace
        all_resources = {}
        for namespace in namespaces:
            all_resources[namespace] = {
                'limits': {
                    'cpu': self._extract_cpu_value(cpu_limits, namespace), 
                    'memory': self._extract_memory_value(memory_limits, namespace)
                },
                'requests': {
                    'cpu': self._extract_cpu_value(cpu_requests, namespace),
                    'memory': self._extract_memory_value(memory_requests, namespace)
                },
                'usage': {
                    'cpu': self._extract_cpu_value(cpu_usage, namespace),
                    'memory': self._extract_memory_value(memory_usage, namespace)
                }
            }

        return all_resources

    def _extract_cpu_value(self, query_result, namespace):
        """Extract and convert CPU values for a specific namespace from the query result."""
        for result in query_result:
            if result["metric"]["namespace"] == namespace:
                raw_value = float(result["value"][1])
                # Convert millicores to cores if necessary (CPU requests/limits)
                # CPU usage (rate) is already in cores, so no conversion needed
                if 'm' in result["value"][1]:  # Only relevant if Prometheus returns millicores
                    return raw_value / 1000
                return raw_value  # already in cores or usage rate
        return 0.0

    def _extract_memory_value(self, query_result, namespace):
        """Extract and convert memory values for a specific namespace from the query result."""
        for result in query_result:
            if result["metric"]["namespace"] == namespace:
                raw_value = float(result["value"][1])
                # Convert bytes to GB
                return raw_value / (1024**2)
        return 0.0
