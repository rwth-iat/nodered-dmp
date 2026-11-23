import base64
from urllib.parse import urlparse

from nodered_dmp.aas.client import get_submodel_element_json, get_submodel_json, id_to_url
from nodered_dmp.model.etl_path import (
    AASAnchor,
    AIDMetadata,
    ETLPath,
    ExtractSpec,
    LoadSpec,
    TransformSpec,
)

# Maps AID endpoint URL schemes to ETLPath protocol names.
# Extend when adding new protocols.
_SCHEME_TO_PROTOCOL: dict[str, str] = {
    "mqtt": "mqtt",
    "opc.tcp": "opcua",
}

_SEM_INTERFACE_REF = (
    "https://admin-shell.io/idta/AssetInterfacesMappingConfiguration/1/0/InterfaceReference"
)
_SEM_SOURCE_SINK_RELATION = (
    "https://admin-shell.io/idta/AssetInterfacesMappingConfiguration/1/0/MappingSourceSinkRelation"
)


def parse_aimc(aimc_url: str, server_base: str, access_token: str | None = None) -> list[ETLPath]:
    """
    Read an AIMC submodel and the referenced AID submodels to build a fully
    populated list[ETLPath]. Each ETLPath covers one source→sink mapping relation.

    Protocols not in _KNOWN_PROTOCOLS are silently skipped.

    access_token, if given, is sent as "Authorization: Bearer <token>" on every
    request to the AAS server.
    """
    aimc_json = get_submodel_json(aimc_url, access_token)
    if _AIMC_V2 in _semantic_id_values(aimc_json):
        return _parse_aimc_v2(aimc_json, server_base, access_token)

    aimc_submodel_id = aimc_json["id"]
    etl_paths: list[ETLPath] = []

    for top_element in aimc_json["submodelElements"]:
        for config_index, mapping_config in enumerate(top_element.get("value", [])):
            _process_mapping_config(
                config_index, mapping_config, aimc_submodel_id, server_base, etl_paths, access_token
            )

    return etl_paths


# --- private helpers ---

def _process_mapping_config(
    config_index: int,
    config: dict,
    aimc_submodel_id: str,
    server_base: str,
    out: list[ETLPath],
    access_token: str | None = None,
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
    interface_json = get_submodel_element_json(interface_url, access_token)

    endpoint_base = _extract_endpoint_base(interface_json)
    if endpoint_base is None:
        return

    scheme = urlparse(endpoint_base).scheme
    protocol = _SCHEME_TO_PROTOCOL.get(scheme)
    if protocol is None:
        return

    for relation_index, relation in enumerate(relation_elements):
        source_keys = relation["first"]["keys"]
        sink_keys = relation["second"]["keys"]

        source_url = _keys_to_url(server_base, source_keys)
        property_json = get_submodel_element_json(source_url, access_token)

        href, control_packet = _extract_forms(property_json)
        if href is None:
            continue
        href = _normalize_href(href, protocol)

        source_idshort_path = _idshort_path(source_keys)
        sink_submodel_id = sink_keys[0]["value"]
        sink_idshort_path = _idshort_path(sink_keys)
        sink_url = _keys_to_url(server_base, sink_keys)
        aimc_idshort_path = f"MappingConfigurations[{config_index}].MappingSourceSinkRelations[{relation_index}]"

        out.append(ETLPath(
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
            aas=AASAnchor(
                aimc_submodel_id=aimc_submodel_id,
                aimc_idshort_path=aimc_idshort_path,
            ),
            aid=_extract_aid_metadata(property_json, aid_submodel_id, source_idshort_path),
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


def _extract_aid_metadata(
    property_json: dict, aid_submodel_id: str, idshort_path: str
) -> AIDMetadata:
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

    return AIDMetadata(
        aid_submodel_id=aid_submodel_id,
        aid_idshort_path=idshort_path,
        title=title,
        data_type=data_type,
        unit=unit,
        observable=observable,
        value_range=value_range,
    )


def _normalize_href(href: str, protocol: str) -> str:
    """Strip protocol-specific URI prefixes that are part of the AID WoT convention but not the raw identifier."""
    if protocol == "opcua" and href.startswith("/?id="):
        return href[5:]
    return href


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

_AIMC_V2 = "https://admin-shell.io/idta/AssetInterfacesMappingConfiguration/2/0/Submodel"
_MEASUREMENT = "https://admin-shell.io/idta/SubmodelTemplate/measurementValue/1/0"


def _children(element: dict) -> dict:
    return {child.get("idShort"): child for child in element.get("value") or []}


def _entry(element: dict, kind: str) -> tuple[str, list[dict]]:
    fields = _children(element)
    return fields[kind + "Id"]["value"], fields[kind]["value"]["keys"]


def _parse_aimc_v2(aimc: dict, base: str, token: str | None) -> list[ETLPath]:
    configs = next((e for e in aimc["submodelElements"] if e.get("idShort") == "MappingConfigurations"), {})
    submodels = {}

    def semantics(submodel_id):
        if submodel_id not in submodels:
            url = id_to_url(base, submodel_id)
            submodels[submodel_id] = _semantic_id_values(get_submodel_json(url, token))
        return submodels[submodel_id]

    paths = []
    targets = set()
    for config_index, config in enumerate(configs.get("value") or []):
        name = f"MappingConfigurations[{config_index}]"
        fields = _children(config)
        try:
            sinks = {}
            for index, sink in enumerate(fields.get("Sinks", {}).get("value") or []):
                identifier, keys = _entry(sink, "Sink")
                if keys[-1]["type"] != "Property" or _MEASUREMENT not in semantics(keys[0]["value"]):
                    continue
                if identifier in sinks:
                    raise ValueError(f"ambiguous MeasurementValue sink for {identifier}")
                sinks[identifier] = (index, keys)
            if not sinks:
                continue

            sources = {}
            for source in fields.get("Sources", {}).get("value") or []:
                identifier, keys = _entry(source, "Source")
                if identifier not in sinks:
                    continue
                interface = get_submodel_element_json(_keys_to_url(base, keys[:2]), token)
                endpoint = _extract_endpoint_base(interface)
                if not endpoint:
                    raise ValueError(f"missing AID endpoint for {identifier}")
                if urlparse(endpoint).scheme != "mqtt":
                    continue
                if identifier in sources:
                    raise ValueError(f"ambiguous MQTT source for {identifier}")
                sources[identifier] = (keys, endpoint)

            if sources and str(fields.get("Transformation", {}).get("value") or "").strip():
                raise ValueError("Lua transformations are not supported")

            for identifier, (keys, endpoint) in sources.items():
                signal = get_submodel_element_json(_keys_to_url(base, keys), token)
                href, control_packet = _extract_forms(signal)
                if not href:
                    raise ValueError(f"missing MQTT topic in forms.href for {identifier}")
                index, target = sinks[identifier]
                sink_url = _keys_to_url(base, target)
                if sink_url in targets:
                    raise ValueError(f"ambiguous mapping to {sink_url}")
                targets.add(sink_url)
                paths.append(ETLPath(
                    extract=ExtractSpec(protocol="mqtt", endpoint=endpoint,
                                        href=href, control_packet=control_packet),
                    transform=TransformSpec(),
                    load=LoadSpec(sink_url=sink_url, submodel_id=target[0]["value"],
                                  idshort_path=_idshort_path(target)),
                    aas=AASAnchor(aimc_submodel_id=aimc["id"],
                                  aimc_idshort_path=f"{name}.Sinks[{index}]", aimc_version="2.0"),
                    aid=_extract_aid_metadata(signal, keys[0]["value"], _idshort_path(keys)),
                ))
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ValueError(f"{name}: {exc}") from exc
    return paths
