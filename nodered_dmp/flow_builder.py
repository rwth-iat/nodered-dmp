import nodered_flowgen as nr

from nodered_dmp.aas_client import get_EndpointMetadata, get_InterfaceMetadata, get_host_and_port


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
        schema, url, port = get_host_and_port(get_EndpointMetadata(submodel_server + connection["interface"]))
        if schema == "mqtt":
            mqtt_broker = nr.MQTTBroker(name="MQTT_Server_1", broker=url, port=port)
            flow.add_node(mqtt_broker)

            for source, sink in connection["source_sink"]:
                topic = get_InterfaceMetadata(submodel_server + source)
                mqtt_in = nr.MQTTIn(topic=topic, qos="2", broker=mqtt_broker.id)
                flow.add_node(mqtt_in, column=0)
                change_1 = nr.Change({
                    "t": "move",
                    "p": "payload",
                    "pt": "msg",
                    "to": "updateValue",
                    "tot": "msg"
                })
                flow.add_node(change_1, column=1)
                flow.connect_nodes(mqtt_in, change_1)
                function_1 = nr.Function("return msg;", name="Custom user function")
                flow.add_node(function_1, column=2)
                flow.connect_nodes(change_1, function_1)
                change_2 = nr.Change({
                    "t": "set",
                    "p": "url",
                    "pt": "msg",
                    "to": submodel_server + sink,
                    "tot": "str"
                })
                flow.add_node(change_2, column=3)
                flow.connect_nodes(function_1, change_2)
                aas_interface_node = subflow_AASInterface.get_instance()
                flow.add_node(aas_interface_node, column=4)
                flow.connect_nodes(change_2, aas_interface_node)

    return flow
