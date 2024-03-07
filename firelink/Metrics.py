import ocviapy
import json
import re

class NamespaceResourceMetrics:

    def _parse_resource_value(self, value, resource_type):
        if value.endswith('m'):
            return float(value[:-1]) / 1000  # Convert millicores to cores
        elif value.endswith('Mi'):
            return float(value[:-2])  # Assume MiB for memory
        elif value.endswith('Gi'):
            return float(value[:-2]) * 1024  # Convert GiB to MiB
        elif value.isdigit():
            if resource_type == 'cpu':
                return float(value)  # Assume cores for CPU
            elif resource_type == 'memory':
                return float(value) / (1024 * 1024)  # Assume bytes and convert to MiB for memory
        else:
            raise ValueError(f"Unsupported resource value: {value}")

    def _aggregate_pod_resources(self, pods):
        resources = {'requests': {'cpu': 0, 'memory': 0}, 'limits': {'cpu': 0, 'memory': 0}}
        for pod in pods['items']:
            for container in pod['spec']['containers']:
                for resource_type, values in container.get('resources', {}).items():
                    for key, value in values.items():
                        if key in ['cpu', 'memory']:
                            resources[resource_type][key] += self._parse_resource_value(value, key)
        return resources

    def _aggregate_usage(self, namespace):
        usage = {'cpu': 0, 'memory': 0}
        command = f"adm top pods -n {namespace} --no-headers".split(" ")
        usage_output = ocviapy.oc(*command).stdout.decode('utf-8').strip().split('\n')
        for line in usage_output:
            parts = line.split()
            if len(parts) >= 3:
                _, cpu_usage, mem_usage = parts[:3]
                usage['cpu'] += self._parse_resource_value(cpu_usage, 'cpu')
                usage['memory'] += self._parse_resource_value(mem_usage, 'memory')
        return usage

    def get_resources_for_namespace(self, namespace):
        command = f"get pods -n {namespace} -o json".split(" ")
        result = ocviapy.oc(*command).stdout.decode('utf-8')
        pods = json.loads(result)

        namespace_resources = self._aggregate_pod_resources(pods)
        namespace_resources['usage'] = self._aggregate_usage(namespace)

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
    def all_top_pods(self):
        result = ocviapy.oc("adm", "top", "pod", "--all-namespaces")
        parsed_result = self._parse_adm_command_result(result)
        return json.dumps(parsed_result)
    
    def top_pods(self, namespace):
        result = ocviapy.oc("adm", "top", "pod", "-n", namespace)
        parsed_result = self._parse_adm_command_result(result)
        return json.dumps(parsed_result)
    
    def top_nodes(self):
        result = ocviapy.oc("adm", "top", "node")
        parsed_result = self._parse_adm_command_result(result)
        return json.dumps(parsed_result)

    def _parse_adm_command_result(self, result):        
        # Check if the command was successful
        if result.exit_code != 0:
            print(f"Error running command: {result.stderr}")
            return None

        # Split the output into lines
        lines = result.stdout.decode("utf-8").strip().split('\n')

        # Extract the headers
        headers = lines[0].split()

        # Parse the remaining lines into a list of dictionaries
        data = []
        for line in lines[1:]:
            values = line.split()
            entry = {header: value for header, value in zip(headers, values)}
            data.append(entry)

        return data

