import nodered_flowgen as nr

from nodered_dmp.model.etl_path import ETLPath
from nodered_dmp.protocols.base import build_chain
from nodered_dmp.protocols.mqtt import SCHEMA as MQTT_SCHEMA

PROTOCOL_SCHEMAS = {
    "mqtt": MQTT_SCHEMA,
}


def build_flow(etl_paths: list[ETLPath]) -> nr.Flow:
    label = etl_paths[0].aimc_submodel_id if etl_paths else "Flow 1"
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
            flow.add_node(config_node)
            config_nodes[config_key] = config_node
        build_chain(schema, flow, subflow, etl_path, config_node=config_node)

    return flow


def _build_aas_interface_subflow(flow: nr.Flow) -> nr.Subflow:
    subflow = nr.Subflow(
        name="AASInterface",
        columns=[120, 320, 520, 770],
        x_offset=200,
        y_offset=140,
    )
    get_property = nr.HTTPRequest(name="get property")
    subflow.add_node(get_property, column=0)
    convert_json = nr.Json()
    subflow.add_node(convert_json, column=1)
    change_value = nr.Change({
        "t": "move",
        "p": "updateValue",
        "pt": "msg",
        "to": "payload.value",
        "tot": "msg",
    })
    subflow.add_node(change_value, column=2)
    put_http_request = nr.HTTPRequest(method="PUT", name="write property")
    subflow.add_node(put_http_request, column=3)
    subflow.connect_to_input(get_property)
    subflow.connect_nodes(get_property, convert_json)
    subflow.connect_nodes(convert_json, change_value)
    subflow.connect_nodes(change_value, put_http_request)
    flow.add_subflow(subflow)
    return subflow
