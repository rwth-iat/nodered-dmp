import nodered_flowgen as nr

from nodered_dmp.aas_client import get_InterfaceMetadata


def add_nodes(flow, subflow_AASInterface, connection, submodel_server, host, port, base_url=None):
    mqtt_broker = nr.MQTTBroker(name="MQTT_Server_1", broker=host, port=port)
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
