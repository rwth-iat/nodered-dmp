import base64
from urllib.parse import urlparse

import requests


def id_to_url(base_url, id):
    return f"{base_url}/submodels/{base64.b64encode(id.encode('utf-8')).decode('utf-8')}"


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
