import nodered_flowgen as nr

from nodered_dmp.model.etl_path import ETLPath
from nodered_dmp.model.store import ETLPathStore
from nodered_dmp.protocols.base import build_chain, restore_headers_rule
from nodered_dmp.protocols.schemas import PROTOCOL_SCHEMAS


def build_flow(etl_paths: list[ETLPath], label: str | None = None, sink_access_token: str | None = None) -> nr.Flow:
    if label is None:
        label = next((p.aas.aimc_submodel_id for p in etl_paths if p.aas), "Flow 1")
    flow = nr.Flow(
        label,
        columns=[170, 470, 770, 1070, 1270, 1470, 1670],
        x_offset=0,
        y_offset=140,
        vertical_spacing=80,
    )

    subflow = _build_aas_interface_subflow(flow)

    config_nodes: dict[tuple[str, str], object] = {}
    for etl_path in etl_paths:
        schema = PROTOCOL_SCHEMAS.get(etl_path.extract.protocol)
        if schema is None:
            continue
        config_key = (etl_path.extract.protocol, etl_path.extract.endpoint)
        config_node = config_nodes.get(config_key)
        if config_node is None and schema.config:
            config_node = schema.config.builds(etl_path)
            if etl_path.nodered and etl_path.nodered.config_node_id:
                config_node.id = etl_path.nodered.config_node_id
            flow.add_node(config_node)
            config_nodes[config_key] = config_node
        build_chain(schema, flow, subflow, etl_path, config_node=config_node, sink_access_token=sink_access_token)

    return flow


def build_and_store_flow(
    etl_paths: list[ETLPath],
    store: ETLPathStore,
    label: str | None = None,
    sink_access_token: str | None = None,
) -> nr.Flow:
    """
    Build a Node-RED flow and persist the updated ETLPaths (with nodered anchors) to the store.

    build_flow populates etl_path.nodered in memory but does not save. This function
    ensures the store reflects the populated anchors immediately after building.
    """
    flow = build_flow(etl_paths, label=label, sink_access_token=sink_access_token)
    for etl_path in etl_paths:
        store.save(etl_path)
    return flow


def _build_aas_interface_subflow(flow: nr.Flow) -> nr.Subflow:
    subflow = nr.Subflow(
        name="AASInterface",
        columns=[120, 270, 420, 570, 720, 870, 1070],
        x_offset=200,
        y_offset=140,
    )
    restore_headers_get = nr.Change(restore_headers_rule())
    subflow.add_node(restore_headers_get, column=0)
    get_property = nr.HTTPRequest(name="get property")
    subflow.add_node(get_property, column=1)
    convert_json = nr.Json()
    subflow.add_node(convert_json, column=2)
    change_value = nr.Change({
        "t": "move",
        "p": "updateValue",
        "pt": "msg",
        "to": "payload.value",
        "tot": "msg",
    })
    subflow.add_node(change_value, column=3)
    to_string = nr.Change({
        "t": "set",
        "p": "payload.value",
        "pt": "msg",
        "to": "$string(payload.value)",
        "tot": "jsonata",
    }, name="toString()")
    subflow.add_node(to_string, column=4)
    restore_headers_put = nr.Change(restore_headers_rule())
    subflow.add_node(restore_headers_put, column=5)
    put_http_request = nr.HTTPRequest(method="PUT", name="write property")
    subflow.add_node(put_http_request, column=6)
    subflow.connect_to_input(restore_headers_get)
    subflow.connect_nodes(restore_headers_get, get_property)
    subflow.connect_nodes(get_property, convert_json)
    subflow.connect_nodes(convert_json, change_value)
    subflow.connect_nodes(change_value, to_string)
    subflow.connect_nodes(to_string, restore_headers_put)
    subflow.connect_nodes(restore_headers_put, put_http_request)
    flow.add_subflow(subflow)
    return subflow
