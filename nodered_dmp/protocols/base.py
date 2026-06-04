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
    builds: Callable                        # (etl_path, config_node | None) → node
    extracts: Callable | None = None        # (node_json) → dict[str, Any] | None
    config_ref_field: str | None = None     # field in this node referencing the config node


@dataclass
class ProtocolSchema:
    protocol: str
    chain: list[NodeSlot]
    config: ConfigSlot | None = None
    anchor_node_type: str = ""  # node type searched for when parsing a flow


def build_chain(
    schema: ProtocolSchema,
    flow,
    subflow,
    etl_path: ETLPath,
    config_node=None,
) -> None:
    """
    Build the node chain for one ETLPath, add nodes to flow, wire them in order,
    and populate etl_path.nodered with the resulting node IDs.

    config_node may be passed in when multiple ETLPaths share the same config
    (e.g. several MQTT topics on the same broker). If None and schema has a
    ConfigSlot, a new config node is created and added to the flow.
    """
    if config_node is None and schema.config:
        config_node = schema.config.builds(etl_path)
        flow.add_node(config_node)

    prev_node = None
    endpoint_node = None
    column_positions: dict[str, int] = {}

    for col, slot in enumerate(schema.chain):
        if slot.node_type == SUBFLOW_INSTANCE:
            node = subflow.get_instance()
        else:
            node = slot.builds(etl_path, config_node)

        flow.add_node(node, column=col)

        if prev_node is not None:
            flow.connect_nodes(prev_node, node)

        if slot.role == "endpoint":
            endpoint_node = node

        column_positions[slot.role] = col
        prev_node = node

    etl_path.nodered = NodeRedAnchor(
        endpoint_node_id=endpoint_node.id,
        config_node_id=config_node.id if config_node else None,
        column_positions=column_positions,
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
    current = start_node

    for i, slot in enumerate(schema.chain):
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

    return extracted
