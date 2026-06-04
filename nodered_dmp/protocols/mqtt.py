from urllib.parse import urlparse

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


def _build_broker(etl) -> nr.MQTTBroker:
    parsed = urlparse(etl.extract.endpoint)
    return nr.MQTTBroker(name="MQTT_Server_1", broker=parsed.hostname, port=parsed.port)


SCHEMA = ProtocolSchema(
    protocol="mqtt",
    anchor_node_type="mqtt in",
    config=ConfigSlot(
        role="broker",
        node_type="mqtt-broker",
        builds=_build_broker,
        extracts=lambda node: {
            "extract.endpoint": f"mqtt://{node['broker']}:{node['port']}"
        },
    ),
    chain=[
        NodeSlot(
            role="endpoint",
            node_type="mqtt in",
            builds=lambda etl, cfg: nr.MQTTIn(
                topic=etl.extract.href, qos="2", broker=cfg.id
            ),
            extracts=lambda node: {"extract.href": node["topic"]},
            config_ref_field="broker",
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
            builds=lambda etl, _: None,  # handled by build_chain
            extracts=None,
        ),
    ],
)
