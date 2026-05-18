import nodered_flowgen as nr

from nodered_dmp.aas_client import get_EndpointMetadata, get_host_and_port
from nodered_dmp.flow_builder.protocols import mqtt, http, modbus, opcua, bacnet

PROTOCOL_HANDLERS = {
    "mqtt": mqtt.add_nodes,
    "http": http.add_nodes,
    "modbus+tcp": modbus.add_nodes,
    "opc.tcp": opcua.add_nodes,
    "bacnet": bacnet.add_nodes,
}


def build_flow(connections, submodel_server):
    flow = nr.Flow("Flow 1", columns=[170, 470, 770, 1070, 1270], x_offset=0, y_offset=140, vertical_spacing=80)

    subflow_AASInterface = nr.Subflow(name="AASInterface", columns=[120, 320, 520, 770], x_offset=200, y_offset=140)
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
        schema, host, port = get_host_and_port(get_EndpointMetadata(submodel_server + connection["interface"]))
        handler = PROTOCOL_HANDLERS.get(schema)
        if handler:
            handler(flow, subflow_AASInterface, connection, submodel_server, host, port)

    return flow
