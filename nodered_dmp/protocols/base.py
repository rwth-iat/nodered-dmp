import json
from dataclasses import dataclass, field
from typing import Any, Callable

from nodered_dmp.model.etl_path import ETLPath, NodeRedAnchor

SUBFLOW_INSTANCE = "subflow:"


class InvalidETLPathError(Exception):
    """Raised when a Node-RED node chain does not match a known ETLPath protocol schema."""


@dataclass
class ConfigSlot:
    role: str
    node_type: str
    builds: Callable        # (etl_path) → config node
    extracts: Callable      # (node_json) → dict[str, Any]


@dataclass
class NodeSlot:
    role: str
    node_type: str                          # exact type, or SUBFLOW_INSTANCE for sink
    builds: Callable                        # (etl_path, config_node | None, sink_access_token | None) → node
    extracts: Callable | None = None        # (node_json) → dict[str, Any] | None
    config_ref_field: str | None = None     # field in this node referencing the config node


@dataclass
class ProtocolSchema:
    protocol: str
    chain: list[NodeSlot]
    config: ConfigSlot | None = None
    anchor_node_type: str = ""  # node type searched for when parsing a flow


def url_set_rules(sink_url: str, sink_access_token: str | None = None) -> list[dict]:
    """Change-node rules for the "url_setter" slot: set msg.url, and stash the
    sink request headers (currently just Authorization, if a token is
    configured) in msg._headers. The AASInterface subflow applies these via
    restore_headers_rule() immediately before each outgoing HTTP request,
    since the "http request" node overwrites msg.headers with the response
    headers of each call."""
    headers: dict[str, str] = {}
    if sink_access_token:
        # CAVEAT: the token is baked into the flow JSON as a plaintext "set"
        # rule (tot="json"), same as the sink URL above. Anyone with access to
        # flow.json or a Node-RED export can read it. For sensitive
        # deployments, replace this with an "env" rule (tot="env") that
        # references an environment variable on the Node-RED runtime instead.
        headers["Authorization"] = f"Bearer {sink_access_token}"
    return [
        {"t": "set", "p": "url", "pt": "msg", "to": sink_url, "tot": "str"},
        {"t": "set", "p": "_headers", "pt": "msg", "to": json.dumps(headers), "tot": "json"},
    ]


def restore_headers_rule() -> dict:
    """Change-node rule that replaces msg.headers with msg._headers. Used
    before each outgoing HTTP request in the AASInterface subflow: a full
    replace (not a merge) so that response headers left over from a prior
    request (e.g. content-length, content-type) don't leak into the next
    request."""
    return {"t": "set", "p": "headers", "pt": "msg", "to": "_headers", "tot": "msg"}


def build_chain(
    schema: ProtocolSchema,
    flow,
    subflow,
    etl_path: ETLPath,
    config_node=None,
    sink_access_token: str | None = None,
) -> None:
    """
    Build the node chain for one ETLPath, add nodes to flow, wire them in order,
    and populate etl_path.nodered with the resulting node IDs.

    config_node may be passed in when multiple ETLPaths share the same config
    (e.g. several MQTT topics on the same broker). If None and schema has a
    ConfigSlot, a new config node is created and added to the flow.

    sink_access_token, if given, is passed through to each slot's builds() so
    the "url_setter" slot can add an Authorization header rule alongside the URL.
    """
    if config_node is None and schema.config:
        config_node = schema.config.builds(etl_path)
        if etl_path.nodered and etl_path.nodered.config_node_id:
            config_node.id = etl_path.nodered.config_node_id
        flow.add_node(config_node)

    prev_node = None
    endpoint_node = None
    column_positions: dict[str, int] = {}
    node_ids: dict[str, str] = {}

    for col, slot in enumerate(schema.chain):
        if slot.node_type == SUBFLOW_INSTANCE:
            node = subflow.get_instance()
        else:
            node = slot.builds(etl_path, config_node, sink_access_token)

        if etl_path.nodered:
            existing_id = etl_path.nodered.node_ids.get(slot.role)
            if existing_id:
                node.id = existing_id

        flow.add_node(node, column=col)

        if prev_node is not None:
            flow.connect_nodes(prev_node, node)

        if slot.role == "endpoint":
            endpoint_node = node

        column_positions[slot.role] = col
        node_ids[slot.role] = node.id
        prev_node = node

    etl_path.nodered = NodeRedAnchor(
        endpoint_node_id=endpoint_node.id,
        config_node_id=config_node.id if config_node else None,
        column_positions=column_positions,
        node_ids=node_ids,
    )


def parse_chain(
    schema: ProtocolSchema,
    start_node: dict[str, Any],
    node_map: dict[str, dict],
    wire_map: dict[str, list[str]],
) -> dict[str, Any]:
    """
    Walk the node chain starting from start_node, validate each node type against
    the schema, and extract ETLPath field values.

    Returns a flat dict mapping ETLPath field paths to their values
    (e.g. {"extract.href": "/device/voltage", "load.sink_url": "http://..."}).

    Raises InvalidETLPathError if the chain structure does not match the schema.
    """
    extracted: dict[str, Any] = {}
    node_ids: dict[str, str] = {}
    current = start_node

    for i, slot in enumerate(schema.chain):
        node_ids[slot.role] = current["id"]
        actual_type = current["type"]

        if slot.node_type == SUBFLOW_INSTANCE:
            if not actual_type.startswith(SUBFLOW_INSTANCE):
                raise InvalidETLPathError(
                    f"Step {i} ({slot.role}): expected subflow instance "
                    f"(type starting with '{SUBFLOW_INSTANCE}'), got '{actual_type}'"
                )
        elif actual_type != slot.node_type:
            raise InvalidETLPathError(
                f"Step {i} ({slot.role}): expected '{slot.node_type}', got '{actual_type}'"
            )

        # If this node references a config node, extract config fields now
        if slot.config_ref_field and schema.config:
            config_id = current.get(slot.config_ref_field)
            config_node = node_map.get(config_id)
            if config_node is None:
                raise InvalidETLPathError(
                    f"Step {i} ({slot.role}): referenced config node '{config_id}' not found"
                )
            if config_node["type"] != schema.config.node_type:
                raise InvalidETLPathError(
                    f"Step {i} ({slot.role}): expected config type "
                    f"'{schema.config.node_type}', got '{config_node['type']}'"
                )
            extracted.update(schema.config.extracts(config_node))
            extracted["nodered.config_node_id"] = config_id

        if slot.extracts:
            extracted.update(slot.extracts(current))

        # Advance to next node (skip for last slot)
        if i < len(schema.chain) - 1:
            next_ids = wire_map.get(current["id"], [])
            if not next_ids:
                raise InvalidETLPathError(
                    f"Step {i} ({slot.role}): no outgoing wire to next node"
                )
            next_node = node_map.get(next_ids[0])
            if next_node is None:
                raise InvalidETLPathError(
                    f"Step {i} ({slot.role}): wired node '{next_ids[0]}' not found"
                )
            current = next_node

    extracted["nodered.node_ids"] = node_ids
    return extracted
