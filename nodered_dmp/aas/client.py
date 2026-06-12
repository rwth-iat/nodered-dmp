import base64
from urllib.parse import urlparse

import requests


def id_to_url(base_url: str, submodel_id: str) -> str:
    b64 = base64.b64encode(submodel_id.encode()).decode()
    return f"{base_url}/submodels/{b64}"


def get_host_and_port(url: str) -> tuple[str, str, int]:
    parsed = urlparse(url)
    return parsed.scheme, parsed.hostname, parsed.port


def _auth_headers(access_token: str | None) -> dict | None:
    if access_token:
        return {"Authorization": f"Bearer {access_token}"}
    return None


def get_submodel_json(url: str, access_token: str | None = None) -> dict:
    return requests.get(url, headers=_auth_headers(access_token)).json()


def get_submodel_element_json(url: str, access_token: str | None = None) -> dict:
    return requests.get(url, headers=_auth_headers(access_token)).json()


def put_submodel(base_url: str, submodel_id: str, body: dict, access_token: str | None = None) -> None:
    b64 = base64.b64encode(submodel_id.encode()).decode()
    requests.put(f"{base_url}/submodels/{b64}", json=body, headers=_auth_headers(access_token))


def put_submodel_element(
    base_url: str, submodel_id: str, idshort_path: str, body: dict, access_token: str | None = None
) -> None:
    b64 = base64.b64encode(submodel_id.encode()).decode()
    requests.put(
        f"{base_url}/submodels/{b64}/submodel-elements/{idshort_path}",
        json=body,
        headers=_auth_headers(access_token),
    )
