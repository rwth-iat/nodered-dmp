from nodered_dmp.aas.client import put_submodel_element
from nodered_dmp.model.etl_path import ETLPath

_SEM = {
    "rdf_type":     "https://www.w3.org/1999/02/22-rdf-syntax-ns#type",
    "wot_title":    "https://www.w3.org/2019/wot/td#title",
    "wot_obs":      "https://www.w3.org/2019/wot/td#isObservable",
    "unit":         "https://schema.org/unitCode",
    "jschema_min":  "https://www.w3.org/2019/wot/json-schema#minimum",
    "jschema_max":  "https://www.w3.org/2019/wot/json-schema#maximum",
    "wot_form":     "https://www.w3.org/2019/wot/td#hasForm",
    "wot_href":     "https://www.w3.org/2019/wot/hypermedia#hasTarget",
    "wot_ct":       "https://www.w3.org/2019/wot/hypermedia#forContentType",
    "prop_aff":     "https://www.w3.org/2019/wot/td#hasPropertyAffordance",
}


def _ref(sem_key: str) -> dict:
    return {"keys": [{"type": "GlobalReference", "value": _SEM[sem_key]}], "type": "ExternalReference"}


def _prop(idshort: str, value: str, value_type: str, sem_key: str | None = None) -> dict:
    node: dict = {"modelType": "Property", "idShort": idshort, "value": value, "valueType": value_type}
    if sem_key:
        node["semanticId"] = _ref(sem_key)
    return node


def build_property_element(etl_path: ETLPath) -> dict:
    """
    Build the SubmodelElementCollection for one AID property (e.g. InterfaceMQTT.InterfaceMetadata.Properties.voltage).
    Requires etl_path.aid to be set.
    """
    aid = etl_path.aid
    if aid is None:
        raise ValueError(f"ETLPath {etl_path.etl_path_id} has no AIDMetadata — cannot build AID property element")

    property_name = aid.aid_idshort_path.split(".")[-1]

    value: list[dict] = [
        _prop("type", aid.data_type or "", "xs:string", "rdf_type"),
        _prop("title", aid.title or property_name, "xs:string", "wot_title"),
        _prop("observable", str(aid.observable).lower(), "xs:boolean", "wot_obs"),
    ]

    if aid.unit is not None:
        value.append(_prop("unit", aid.unit, "xs:string", "unit"))

    if aid.value_range is not None:
        min_val, max_val = aid.value_range
        value.append({
            "modelType": "Range",
            "idShort": "range",
            "valueType": "xs:integer",
            "min": min_val,
            "max": max_val,
            "semanticId": _ref("jschema_min"),
            "supplementalSemanticIds": [_ref("jschema_max")],
        })

    forms_value: list[dict] = [
        _prop("href", etl_path.extract.href, "xs:string", "wot_href"),
    ]
    if etl_path.extract.control_packet:
        forms_value.append(_prop("mqv_controlPacket", etl_path.extract.control_packet, "xs:string"))
    forms_value.append(_prop("contentType", "application/json", "xs:string", "wot_ct"))

    value.append({
        "modelType": "SubmodelElementCollection",
        "idShort": "forms",
        "semanticId": _ref("wot_form"),
        "value": forms_value,
    })

    return {
        "modelType": "SubmodelElementCollection",
        "idShort": property_name,
        "semanticId": _ref("prop_aff"),
        "value": value,
    }


def write_aid_properties(etl_paths: list[ETLPath], server_base: str) -> None:
    """PUT each property element to the AAS server. Paths without AIDMetadata are skipped."""
    for etl_path in etl_paths:
        if etl_path.aid is None:
            continue
        body = build_property_element(etl_path)
        put_submodel_element(server_base, etl_path.aid.aid_submodel_id, etl_path.aid.aid_idshort_path, body)
