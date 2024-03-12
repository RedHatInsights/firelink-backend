import ocviapy
import json
import re
from kubernetes import client, config


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
        metrics = self.custom_api.list_cluster_custom_object(
            group="metrics.k8s.io",
            version="v1beta1",
            plural="pods"
        )
        parsed_metrics = self._parse_pod_metrics(metrics)
        return parsed_metrics

    def top_pods(self, namespace):
        metrics = self.custom_api.list_namespaced_custom_object(
            group="metrics.k8s.io",
            version="v1beta1",
            namespace=namespace,
            plural="pods"
        )
        parsed_metrics = self._parse_pod_metrics(metrics)
        return parsed_metrics

    def top_nodes(self):
        metrics = self.custom_api.list_cluster_custom_object(
            group="metrics.k8s.io",
            version="v1beta1",
            plural="nodes"
        )
        parsed_metrics = self._parse_node_metrics(metrics)
        return parsed_metrics

    def _parse_pod_metrics(self, metrics):
        parsed_metrics = []
        for item in metrics["items"]:
            pod_name = item["metadata"]["name"]
            namespace = item["metadata"]["namespace"]
            cpu_usage = item["containers"][0]["usage"]["cpu"]
            memory_usage = item["containers"][0]["usage"]["memory"]
            entry = {
                "NAME": f"{namespace}/{pod_name}",
                "CPU(cores)": cpu_usage,
                "MEMORY(bytes)": memory_usage
            }
            parsed_metrics.append(entry)
        return parsed_metrics

    def _parse_node_metrics(self, metrics):
        parsed_metrics = []
        v1_api = client.CoreV1Api()
        for item in metrics["items"]:
            node_name = item["metadata"]["name"]
            cpu_usage = item["usage"]["cpu"]
            memory_usage = item["usage"]["memory"]

            # Fetch the node information to get the allocatable resources
            node_info = v1_api.read_node(node_name)
            allocatable_cpu = node_info.status.allocatable["cpu"]
            allocatable_memory = node_info.status.allocatable["memory"]

            # Calculate CPU and memory percentages
            cpu_percentage = f"{int(item['usage']['cpu'].replace('m', '')) / int(allocatable_cpu.replace('m', '')) * 100:.2f}%"
            memory_percentage = f"{int(item['usage']['memory'].replace('Ki', '')) / int(allocatable_memory.replace('Ki', '')) * 100:.2f}%"

            entry = {
                "NAME": node_name,
                "CPU(cores)": cpu_usage,
                "CPU%": cpu_percentage,
                "MEMORY(bytes)": memory_usage,
                "MEMORY%": memory_percentage
            }
            parsed_metrics.append(entry)
        return parsed_metrics

