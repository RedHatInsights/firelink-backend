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

