import base64
from urllib.parse import urlparse

import requests


def id_to_url(base_url: str, submodel_id: str) -> str:
    b64 = base64.b64encode(submodel_id.encode()).decode()
    return f"{base_url}/submodels/{b64}"


def get_host_and_port(url: str) -> tuple[str, str, int]:
    parsed = urlparse(url)
    return parsed.scheme, parsed.hostname, parsed.port


def get_submodel_json(url: str) -> dict:
    return requests.get(url).json()


def get_submodel_element_json(url: str) -> dict:
    return requests.get(url).json()
