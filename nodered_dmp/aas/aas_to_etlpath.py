import base64
from urllib.parse import urlparse

from nodered_dmp.aas.client import get_submodel_element_json, get_submodel_json
from nodered_dmp.model.etl_path import (
    AASAnchor,
    ETLPath,
    ExtractSpec,
    LoadSpec,
    TransformSpec,
)

# Expand as protocol parsers are implemented in nodered_dmp/protocols/
_KNOWN_PROTOCOLS = {"mqtt"}

_SEM_INTERFACE_REF = (
    "https://admin-shell.io/idta/AssetInterfacesMappingConfiguration/1/0/InterfaceReference"
)
_SEM_SOURCE_SINK_RELATION = (
    "https://admin-shell.io/idta/AssetInterfacesMappingConfiguration/1/0/MappingSourceSinkRelation"
)


def parse_aimc(aimc_url: str, server_base: str) -> list[ETLPath]:
    """
    Read an AIMC submodel and the referenced AID submodels to build a fully
    populated list[ETLPath]. Each ETLPath covers one source→sink mapping relation.

    Protocols not in _KNOWN_PROTOCOLS are silently skipped.
    """
    aimc_json = get_submodel_json(aimc_url)
    aimc_submodel_id = aimc_json["id"]
    etl_paths: list[ETLPath] = []

    for top_element in aimc_json["submodelElements"]:
        for mapping_config in top_element.get("value", []):
            _process_mapping_config(
                mapping_config, aimc_submodel_id, server_base, etl_paths
            )

    return etl_paths


# --- private helpers ---

def _process_mapping_config(
    config: dict, aimc_submodel_id: str, server_base: str, out: list[ETLPath]
) -> None:
    interface_keys = None
    relation_elements = []

    for element in config.get("value", []):
        if _SEM_INTERFACE_REF in _semantic_id_values(element):
            interface_keys = element["value"]["keys"]
        if _SEM_SOURCE_SINK_RELATION in _semantic_id_list_element_values(element):
            relation_elements = element.get("value", [])

    if not interface_keys or not relation_elements:
        return

    aid_submodel_id = interface_keys[0]["value"]
    interface_url = _keys_to_url(server_base, interface_keys)
    interface_json = get_submodel_element_json(interface_url)

    endpoint_base = _extract_endpoint_base(interface_json)
    if endpoint_base is None:
        return

    protocol = urlparse(endpoint_base).scheme
    if protocol not in _KNOWN_PROTOCOLS:
        return

    for relation in relation_elements:
        source_keys = relation["first"]["keys"]
        sink_keys = relation["second"]["keys"]

        source_url = _keys_to_url(server_base, source_keys)
        property_json = get_submodel_element_json(source_url)

        href, control_packet = _extract_forms(property_json)
        if href is None:
            continue

        source_idshort_path = _idshort_path(source_keys)
        sink_submodel_id = sink_keys[0]["value"]
        sink_idshort_path = _idshort_path(sink_keys)
        sink_url = _keys_to_url(server_base, sink_keys)

        out.append(ETLPath(
            aimc_submodel_id=aimc_submodel_id,
            aimc_idshort_path=source_idshort_path,
            extract=ExtractSpec(
                protocol=protocol,
                endpoint=endpoint_base,
                href=href,
                control_packet=control_packet,
            ),
            transform=TransformSpec(),
            load=LoadSpec(
                sink_url=sink_url,
                submodel_id=sink_submodel_id,
                idshort_path=sink_idshort_path,
            ),
            aas=_extract_aas_anchor(property_json, aid_submodel_id, source_idshort_path),
        ))


def _keys_to_url(server_base: str, keys: list[dict]) -> str:
    submodel_id = keys[0]["value"]
    b64 = base64.b64encode(submodel_id.encode()).decode()
    path = _idshort_path(keys)
    return f"{server_base}/submodels/{b64}/submodel-elements/{path}"


def _idshort_path(keys: list[dict]) -> str:
    return ".".join(k["value"] for k in keys[1:])


def _extract_endpoint_base(interface_json: dict) -> str | None:
    for elem in interface_json.get("value", []):
        if elem.get("idShort") == "EndpointMetadata":
            for sub in elem.get("value", []):
                if sub.get("idShort") == "base":
                    return sub.get("value")
    return None


def _extract_forms(property_json: dict) -> tuple[str | None, str | None]:
    for elem in property_json.get("value", []):
        if elem.get("idShort") == "forms":
            href = None
            control_packet = None
            for sub in elem.get("value", []):
                if sub.get("idShort") == "href":
                    href = sub.get("value")
                elif sub.get("idShort") == "mqv_controlPacket":
                    control_packet = sub.get("value")
            return href, control_packet
    return None, None


def _extract_aas_anchor(
    property_json: dict, aid_submodel_id: str, idshort_path: str
) -> AASAnchor:
    by_idshort = {e.get("idShort"): e for e in property_json.get("value", [])}

    title = by_idshort.get("title", {}).get("value")
    data_type = by_idshort.get("type", {}).get("value")
    unit = by_idshort.get("unit", {}).get("value") or None

    observable_str = by_idshort.get("observable", {}).get("value", "false")
    observable = str(observable_str).lower() == "true"

    value_range = None
    range_elem = next(
        (e for e in property_json.get("value", []) if e.get("modelType") == "Range"),
        None,
    )
    if range_elem and range_elem.get("min") and range_elem.get("max"):
        value_range = (range_elem["min"], range_elem["max"])

    return AASAnchor(
        aid_submodel_id=aid_submodel_id,
        aid_idshort_path=idshort_path,
        title=title,
        data_type=data_type,
        unit=unit,
        observable=observable,
        value_range=value_range,
    )


def _semantic_id_values(element: dict) -> list[str]:
    sem = element.get("semanticId")
    if not isinstance(sem, dict):
        return []
    return [k["value"] for k in sem.get("keys", [])]


def _semantic_id_list_element_values(element: dict) -> list[str]:
    sem = element.get("semanticIdListElement")
    if not isinstance(sem, dict):
        return []
    return [k["value"] for k in sem.get("keys", [])]
