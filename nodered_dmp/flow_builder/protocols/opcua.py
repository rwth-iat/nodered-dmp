import nodered_flowgen as nr

from nodered_dmp.aas_client import get_InterfaceMetadata


def add_nodes(flow, subflow_AASInterface, connection, submodel_server, host, port, base_url=None):
    opcua_endpoint = nr.OpcUaEndpoint(
        endpoint=base_url or f"opc.tcp://{host}:{port}",
        name="OPC UA Server",
    )
    flow.add_node(opcua_endpoint)

    inject = nr.Inject(payload="true", payload_type="bool", repeat="0.5")
    flow.add_node(inject, column=0)

    for source, sink in connection["source_sink"]:
        node_id = get_InterfaceMetadata(submodel_server + source)
        opcua_item = nr.OpcUaItem(item=node_id)
        flow.add_node(opcua_item, column=1)
        flow.connect_nodes(inject, opcua_item)
        opcua_client = nr.OpcUaClient(endpoint=opcua_endpoint.id)
        flow.add_node(opcua_client, column=2)
        flow.connect_nodes(opcua_item, opcua_client)
        change_1 = nr.Change({
            "t": "move",
            "p": "payload",
            "pt": "msg",
            "to": "updateValue",
            "tot": "msg",
        })
        flow.add_node(change_1, column=3)
        flow.connect_nodes(opcua_client, change_1)
        function_1 = nr.Function("return msg;", name="Custom user function")
        flow.add_node(function_1, column=4)
        flow.connect_nodes(change_1, function_1)
        change_2 = nr.Change({
            "t": "set",
            "p": "url",
            "pt": "msg",
            "to": submodel_server + sink,
            "tot": "str",
        })
        flow.add_node(change_2, column=5)
        flow.connect_nodes(function_1, change_2)
        aas_interface_node = subflow_AASInterface.get_instance()
        flow.add_node(aas_interface_node, column=6)
        flow.connect_nodes(change_2, aas_interface_node)
