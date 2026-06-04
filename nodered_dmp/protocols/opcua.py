import nodered_flowgen as nr

from nodered_dmp.protocols.base import SUBFLOW_INSTANCE, ConfigSlot, NodeSlot, ProtocolSchema

_MOVE_PAYLOAD_RULE = {
    "t": "move",
    "p": "payload",
    "pt": "msg",
    "to": "updateValue",
    "tot": "msg",
}


def _url_set_rule(sink_url: str) -> dict:
    return {"t": "set", "p": "url", "pt": "msg", "to": sink_url, "tot": "str"}


SCHEMA = ProtocolSchema(
    protocol="opcua",
    anchor_node_type="OpcUa-Item",
    config=ConfigSlot(
        role="server",
        node_type="OpcUa-Endpoint",
        builds=lambda etl: nr.OpcUaEndpoint(
            endpoint=etl.extract.endpoint,
            name="OPC_UA_Server",
        ),
        extracts=lambda node: {
            "extract.endpoint": node["endpoint"]
        },
    ),
    chain=[
        NodeSlot(
            role="endpoint",
            node_type="OpcUa-Item",
            builds=lambda etl, cfg: nr.OpcUaItem(item=etl.extract.href),
            extracts=lambda node: {"extract.href": node["item"]},
        ),
        NodeSlot(
            role="client",
            node_type="OpcUa-Client",
            builds=lambda etl, cfg: nr.OpcUaClient(
                endpoint=cfg.id,
                action="subscribe",
            ),
            extracts=None,
            config_ref_field="endpoint",
        ),
        NodeSlot(
            role="pre_change",
            node_type="change",
            builds=lambda etl, _: nr.Change(_MOVE_PAYLOAD_RULE),
            extracts=None,
        ),
        NodeSlot(
            role="transform",
            node_type="function",
            builds=lambda etl, _: nr.Function(
                etl.transform.function_code, name="Custom user function"
            ),
            extracts=lambda node: {"transform.function_code": node["func"]},
        ),
        NodeSlot(
            role="url_setter",
            node_type="change",
            builds=lambda etl, _: nr.Change(_url_set_rule(etl.load.sink_url)),
            extracts=lambda node: {"load.sink_url": node["rules"][0]["to"]},
        ),
        NodeSlot(
            role="sink",
            node_type=SUBFLOW_INSTANCE,
            builds=lambda etl, _: None,
            extracts=None,
        ),
    ],
)
