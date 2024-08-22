import re
from kubernetes import client, config
from prometheus_api_client import PrometheusConnect
import os
import warnings
from urllib3.exceptions import InsecureRequestWarning
import urllib3

# Suppress only the specific InsecureRequestWarning from urllib3
warnings.simplefilter('ignore', InsecureRequestWarning)
# Disable all urllib3 warnings
urllib3.disable_warnings(InsecureRequestWarning)

class PodQueries:
    def pod_cpu_usage(self, namespace):
        return f'sum(node_namespace_pod_container:container_cpu_usage_seconds_total:sum_irate{{cluster="", namespace="{namespace}"}}) by (pod)'
    def pod_memory_usage(self, namespace):
        return f'sum(container_memory_working_set_bytes{{namespace="{namespace}"}}) by (pod)'

class MemoryQueries:
    def limits(self, namespaces):
        return f'sum by (namespace) (kube_pod_resource_limit{{resource="memory", namespace=~"{namespaces}"}})'

    def requests(self, namespaces):
        return f'sum by (namespace) (kube_pod_resource_request{{resource="memory", namespace=~"{namespaces}"}})'

    def usage(self, namespaces):
        return f'sum(container_memory_working_set_bytes{{namespace=~"{namespaces}",container="",pod!=""}}) BY (namespace)'

class CPUQueries:
    def limits(self, namespaces):
        return f'sum by (namespace) (kube_pod_resource_limit{{resource="cpu", namespace=~"{namespaces}"}})'

    def requests(self, namespaces):
        return f'sum by (namespace) (kube_pod_resource_request{{resource="cpu", namespace=~"{namespaces}"}})'

    def usage(self, namespaces):
        return f'sum(rate(container_cpu_usage_seconds_total{{namespace=~"{namespaces}",container!="POD"}}[5m])) by (namespace)'

class PrometheusPodMetrics:
    def __init__(self):
        prometheus_url = "https://prometheus.crcd01ue1.devshift.net"
        bearer_token = os.getenv("OC_TOKEN")
        self.prometheus_api = PrometheusConnect(
            url=prometheus_url,
            headers={"Authorization": f"Bearer {bearer_token}"},
            disable_ssl=True
        )
    
    def top_pods(self, namespace):
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
    def __init__(self):
        prometheus_url = "https://prometheus.crcd01ue1.devshift.net"
        bearer_token = os.getenv("OC_TOKEN")
        self.prometheus_api = PrometheusConnect(
            url=prometheus_url,
            headers={"Authorization": f"Bearer {bearer_token}"},
            disable_ssl=True
        )

    def _run_query(self, query):
        """Run a Prometheus query and return the results."""
        try:
            results = self.prometheus_api.custom_query(query=query)
            return results
        except Exception as e:
            print(f"Error running query: {e}")
            return None

    def get_resources_for_namespace(self, namespace):
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

# Example usage:
if __name__ == "__main__":
    namespaces = ["namespace1", "namespace2", "namespace3"]  # Add your namespaces here
    prometheus_metrics = PrometheusNamespaceMetrics()
    resources = prometheus_metrics.get_resources_for_namespaces(namespaces)
    print(resources)

        

class NamespaceResourceMetrics:

    def __init__(self):
        config.load_kube_config()
        self.v1 = client.CoreV1Api()
        self.metrics_api = client.CustomObjectsApi()

    def _parse_resource_value(self, value, resource_type):
        if value.endswith('m'):
            return float(value[:-1]) / 1000  # Convert millicores to cores
        elif value.endswith('Ki'):
            if resource_type == 'cpu':
                raise ValueError(f"Unsupported CPU value format: {value}")
            elif resource_type == 'memory':
                return float(value[:-2]) / 1024  # Convert KiB to MiB
        elif value.endswith('Mi'):
            if resource_type == 'cpu':
                raise ValueError(f"Unsupported CPU value format: {value}")
            elif resource_type == 'memory':
                return float(value[:-2])  # Assume MiB for memory
        elif value.endswith('Gi'):
            if resource_type == 'cpu':
                raise ValueError(f"Unsupported CPU value format: {value}")
            elif resource_type == 'memory':
                return float(value[:-2]) * 1024  # Convert GiB to MiB
        else:
            try:
                float_value = float(value)
                if resource_type == 'cpu':
                    return float_value  # Assume cores for CPU
                elif resource_type == 'memory':
                    return float_value / (1024 * 1024)  # Assume bytes and convert to MiB for memory
            except ValueError:
                raise ValueError(f"Unsupported resource value: {value}")

    def _aggregate_pod_resources(self, pods):
        resources = {'requests': {'cpu': 0, 'memory': 0}, 'limits': {'cpu': 0, 'memory': 0}}

        for pod in pods:
            for container in pod.spec.containers:
                if container.resources is not None:
                    for resource_type in ['requests', 'limits']:
                        if resource_type in container.resources.to_dict():
                            values = container.resources.to_dict()[resource_type]
                            for key, value in values.items():
                                if key in ['cpu', 'memory']:
                                    resources[resource_type][key] += self._parse_resource_value(value, key)


    def _aggregate_usage(self, namespace):
        usage = {'cpu': 0, 'memory': 0}

        try:
            metrics = self.metrics_api.list_namespaced_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                namespace=namespace,
                plural="pods"
            )

            for pod_metrics in metrics['items']:
                for container_metrics in pod_metrics['containers']:
                    cpu_usage = container_metrics['usage']['cpu']
                    mem_usage = container_metrics['usage']['memory']
                    usage['cpu'] += self._parse_resource_value(cpu_usage, 'cpu')
                    usage['memory'] += self._parse_resource_value(mem_usage, 'memory')

        except client.rest.ApiException as e:
            print(f"Error retrieving pod usage metrics for namespace {namespace}: {e}")

        return usage

    def get_resources_for_namespace(self, namespace):
        namespace_resources = {'limits': {'cpu': 0, 'memory': 0}, 'requests': {'cpu': 0, 'memory': 0}}

        try:
            pods = self.v1.list_namespaced_pod(namespace)
            for pod in pods.items:
                for container in pod.spec.containers:
                    if container.resources is not None:
                        for resource_type in ['requests', 'limits']:
                            if resource_type in container.resources.to_dict():
                                values = container.resources.to_dict()[resource_type]
                                for key, value in values.items():
                                    if key in ['cpu', 'memory']:
                                        namespace_resources[resource_type][key] += self._parse_resource_value(value, key)
        except Exception as e:
            print(f"Error retrieving pod resources for namespace {namespace}: {e}")

        try:
            namespace_resources['usage'] = self._aggregate_usage(namespace)
        except Exception as e:
            print(f"Error retrieving pod usage for namespace {namespace}: {e}")
            namespace_resources['usage'] = {'cpu': 0, 'memory': 0}  # Set default usage values

        # Round the values to 2 decimal places
        for resource_type in namespace_resources:
            for key in namespace_resources[resource_type]:
                namespace_resources[resource_type][key] = round(namespace_resources[resource_type][key], 2)

        return namespace_resources
        
    def get_resources_for_namespaces(self, namespaces):
        all_resources = {}
        for namespace in namespaces:
            all_resources[namespace] = self.get_resources_for_namespace(namespace)
        return all_resources

class ClusterResourceMetrics:
    def __init__(self):
        config.load_kube_config()
        self.custom_api = client.CustomObjectsApi()

    def all_top_pods(self):
        metrics = self.custom_api.list_cluster_custom_object(group="metrics.k8s.io", version="v1beta1", plural="pods")
        return self._parse_pod_metrics(metrics)

    def top_pods(self, namespace):
        metrics = self.custom_api.list_namespaced_custom_object(group="metrics.k8s.io", version="v1beta1", namespace=namespace, plural="pods")
        return self._parse_pod_metrics(metrics)

    def top_nodes(self):
        metrics = self.custom_api.list_cluster_custom_object(group="metrics.k8s.io", version="v1beta1", plural="nodes")
        return self._parse_node_metrics(metrics)

    def _parse_pod_metrics(self, metrics):
        return [
            {"NAME": f"{item['metadata']['namespace']}/{item['metadata']['name']}",
             "CPU(cores)": item["containers"][0]["usage"]["cpu"],
             "MEMORY(bytes)": self._convert_to_gi(item["containers"][0]["usage"]["memory"])}
            for item in metrics["items"]
        ]

    def _parse_node_metrics(self, metrics):
        v1_api = client.CoreV1Api()
        parsed_metrics = []
        for item in metrics["items"]:
            node_name = item["metadata"]["name"]
            try:
                node_info = v1_api.read_node(node_name)
                parsed_metrics.append({
                    "NAME": node_name,
                    "CPU(cores)": item["usage"]["cpu"],
                    "CPU%": self._calculate_percentage(item["usage"]["cpu"], node_info.status.allocatable["cpu"]),
                    "MEMORY(bytes)": self._convert_to_gi(item["usage"]["memory"]),
                    "MEMORY%": self._calculate_percentage(item["usage"]["memory"], node_info.status.allocatable["memory"])
                })
            except client.rest.ApiException as e:
                print(f"API error for node {node_name}: {e}")
            except ValueError as e:
                print(f"Value error processing metrics for node {node_name}: {e}")
        return parsed_metrics

    def _convert_to_gi(self, value):
        if value == '0':
            return '0Gi'
        units = {"Ki": 1/1024/1024, "Mi": 1/1024, "Gi": 1}
        match = re.match(r"(\d+)(Ki|Mi|Gi)", value)
        if match:
            return f"{int(match.group(1)) * units[match.group(2)]:.2f}Gi"
        raise ValueError(f"Unsupported memory unit in '{value}'")


    def _calculate_percentage(self, usage, allocatable):
        usage_value = self._convert_to_base_unit(usage)
        allocatable_value = self._convert_to_base_unit(allocatable)
        if allocatable_value == 0:
            return "0%"
        return f"{(usage_value / allocatable_value) * 100:.2f}%"

    def _convert_to_base_unit(self, value):
        units = {"Ki": 1, "Mi": 1024, "Gi": 1024*1024}
        match = re.match(r"(\d+)(Ki|Mi|Gi|m)?", value)
        if match:
            unit = match.group(2) or "Ki"  # Assume "Ki" if no unit is present, "m" is treated as "Ki"
            return int(match.group(1)) * units.get(unit, 1)
        raise ValueError(f"Invalid resource value '{value}'")

