from nodered_dmp.protocols.mqtt import SCHEMA as MQTT_SCHEMA

ALL_SCHEMAS = [MQTT_SCHEMA]

PROTOCOL_SCHEMAS = {schema.protocol: schema for schema in ALL_SCHEMAS}

ANCHOR_TYPE_TO_SCHEMA = {
    schema.anchor_node_type: schema
    for schema in ALL_SCHEMAS
    if schema.anchor_node_type
}
