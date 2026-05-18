import json
from tarfile import is_tarfile
from textwrap import indent

import aas_python_http_client
from aas_python_http_client import ApiClient, Configuration, AssetAdministrationShellRepositoryAPIApi, SubmodelRepositoryAPIApi

import requests
import base64
from urllib.parse import urlparse


def get_host_and_port(url: str):
    parsed = urlparse(url)
    return parsed.scheme, parsed.hostname, parsed.port


def get_submodel_json(url):
    response = requests.get(url)
    return response.json()

def get_submodel_element_json(url):
    pass

def get_mapping_relations(json_obj):
    mapping_config_url = json_obj.get("value", {}).get("href")
    response = requests.get(mapping_config_url)
    return response.json()

def id_to_url(base_URL,id):
    return f"{base_URL}/submodels/{base64.b64encode(id.encode('utf-8')).decode('utf-8')}"


def resolve_relationship_to_reference(keys):
    if keys[0].get("type") == "Submodel":
        element_ref = "/submodels"
        submodel_id = keys.pop(0).get("value")
        base64_id = base64.b64encode(submodel_id.encode('utf-8')).decode('utf-8')
        element_ref = f"{element_ref}/{base64_id}/submodel-elements"
    else:
        raise Exception(
            f"First element of the relationship is not a Submodel")
    first_submodel_element = True
    for key in keys:
        delimiter = "."
        if first_submodel_element:
            delimiter = "/"
            first_submodel_element = False
        element_value = key.get("value")
        element_ref = f"{element_ref}{delimiter}{element_value}"
    return element_ref

def get_connections(AIMC_url):
    AIMC_json = get_submodel_json(AIMC_url)
    connections = []
    for index_1, submodelElement in enumerate(AIMC_json.get("submodelElements")):
        idShort = submodelElement.get("idShort")
        for value in submodelElement.get("value"):
            connection = {"source_sink": []}
            for value_in_value in value.get("value"):
                semantic_ids = []

                if type(value_in_value.get("semanticId")) is dict:
                    for key in value_in_value.get("semanticId").get("keys"):
                        semantic_ids.append(key.get("value", ""))
                if "https://admin-shell.io/idta/AssetInterfacesMappingConfiguration/1/0/InterfaceReference" in semantic_ids:
                    interface_in_aas = resolve_relationship_to_reference(value_in_value.get("value").get("keys"))
                    connection["interface"] = interface_in_aas

                if type(value_in_value.get("semanticIdListElement")) is dict:
                    for key in value_in_value.get("semanticIdListElement").get("keys"):
                        semantic_ids.append(key.get("value", ""))
                if "https://admin-shell.io/idta/AssetInterfacesMappingConfiguration/1/0/MappingSourceSinkRelation" in semantic_ids:
                    for index_2, relationship in enumerate(value_in_value.get("value")):
                        source_in_aas = resolve_relationship_to_reference(relationship.get("first").get("keys"))
                        sink_in_aas = resolve_relationship_to_reference(relationship.get("second").get("keys"))
                        connection["source_sink"].append((source_in_aas, sink_in_aas))
            connections.append(connection)
    return connections


def get_EndpointMetadata(url):
    response = requests.get(url)
    for value in response.json()["value"]:
        if value["idShort"] == "EndpointMetadata":
            for value_in_value in value["value"]:
                if value_in_value["idShort"] == "base":
                    return value_in_value["value"]
  

def get_InterfaceMetadata(url):
    response = requests.get(url)
    for value in response.json()["value"]:
        if value["idShort"] == "forms":
            for value_in_value in value["value"]:
                if value_in_value["idShort"] == "href":
                    return value_in_value["value"]
                


# Example usage:
if __name__ == "__main__":
    AAS_SERVER = "http://localhost:8081"
    SUBMODEL_SERVER = "http://localhost:8081"

    AIMC_id = "https://example.com/ids/sm/AssetInterfacesMappingConfiguration"
    AIMC_url = id_to_url(SUBMODEL_SERVER, AIMC_id)
    connections = get_connections(AIMC_url)


    import nodered_flowgen as nr

    # Create a new flow with default grid settings.
    flow = nr.Flow("Flow 1", columns=[170, 470, 770, 1070, 1270], x_offset=0, y_offset=140, vertical_spacing=80)
    subflow_AASInterface = nr.Subflow(name="AASInterface", columns=[120, 320, 520, 770], x_offset=200, y_offset=140,)
    get_property = nr.HTTPRequest(name="get property")
    subflow_AASInterface.add_node(get_property, column=0)
    convert_json = nr.Json()
    subflow_AASInterface.add_node(convert_json, column=1)
    change_ValueinJson = nr.Change({
        "t": "move",
        "p": "updateValue",
        "pt": "msg",
        "to": "payload.value",
        "tot": "msg"
    })
    subflow_AASInterface.add_node(change_ValueinJson, column=2)
    put_http_request = nr.HTTPRequest(method="PUT", name="write property")
    subflow_AASInterface.add_node(put_http_request, column=3)
    subflow_AASInterface.connect_to_input(get_property)
    subflow_AASInterface.connect_nodes(get_property, convert_json)
    subflow_AASInterface.connect_nodes(convert_json, change_ValueinJson)
    subflow_AASInterface.connect_nodes(change_ValueinJson, put_http_request)
    flow.add_subflow(subflow_AASInterface)

    for connection in connections:
        schema, url, port = get_host_and_port(get_EndpointMetadata(SUBMODEL_SERVER + connection["interface"]))
        if schema == "mqtt":
            mqtt_broker_1 = nr.MQTTBroker(name="MQTT_Server_1", broker=url, port=port)
            flow.add_node(mqtt_broker_1)    

            for source, sink in connection["source_sink"]:
                topic = get_InterfaceMetadata(SUBMODEL_SERVER + source)
                mqtt_in_1 = nr.MQTTIn(topic=topic, qos="2", broker=mqtt_broker_1.id)
                flow.add_node(mqtt_in_1, column=0)
                change_1 = nr.Change({
                    "t": "move",
                    "p": "payload",
                    "pt": "msg",
                    "to": "updateValue",
                    "tot": "msg"
                })
                flow.add_node(change_1, column=1)
                flow.connect_nodes(mqtt_in_1, change_1)
                function_1 = nr.Function("return msg;",name="Custom user function")
                flow.add_node(function_1, column=2)
                flow.connect_nodes(change_1, function_1)
                change_2 = nr.Change({
                    "t": "set",
                    "p": "url",
                    "pt": "msg",
                    "to": SUBMODEL_SERVER + sink,
                    "tot": "str"
                })
                flow.add_node(change_2, column=3)
                flow.connect_nodes(function_1, change_2)
                AASInterface_node = subflow_AASInterface.get_instance()
                flow.add_node(AASInterface_node, column=4)
                flow.connect_nodes(change_2, AASInterface_node)

    # Generate and print the JSON flow.
    print(flow.generate_json())




