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


def put_submodel(base_url: str, submodel_id: str, body: dict) -> None:
    b64 = base64.b64encode(submodel_id.encode()).decode()
    requests.put(f"{base_url}/submodels/{b64}", json=body)


def put_submodel_element(base_url: str, submodel_id: str, idshort_path: str, body: dict) -> None:
    b64 = base64.b64encode(submodel_id.encode()).decode()
    requests.put(f"{base_url}/submodels/{b64}/submodel-elements/{idshort_path}", json=body)
