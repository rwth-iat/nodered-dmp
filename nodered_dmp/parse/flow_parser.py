from typing import Any

from nodered_dmp.model.etl_path import ETLPath, ExtractSpec, LoadSpec, NodeRedAnchor, TransformSpec
from nodered_dmp.protocols.base import InvalidETLPathError, ProtocolSchema, parse_chain
from nodered_dmp.protocols.schemas import ANCHOR_TYPE_TO_SCHEMA


def parse_flow(nodes: list[dict[str, Any]]) -> list[ETLPath]:
    """
    Parse a Node-RED flow JSON array into a list of ETLPath objects.

    For each node whose type matches a known anchor_node_type, the chain is
    walked backwards to its start, then validated forward against the schema.
    Chains that do not match any schema are silently skipped.
    """
    node_map = {n["id"]: n for n in nodes}
    wire_map = _build_wire_map(nodes)
    reverse_wire_map = _build_reverse_wire_map(nodes)

    etl_paths = []
    visited_starts: set[str] = set()

    for node in nodes:
        schema = ANCHOR_TYPE_TO_SCHEMA.get(node["type"])
        if schema is None:
            continue

        start = _walk_to_start(node, reverse_wire_map, node_map)
        if start["id"] in visited_starts:
            continue
        visited_starts.add(start["id"])

        try:
            extracted = parse_chain(schema, start, node_map, wire_map)
        except InvalidETLPathError:
            continue

        etl_paths.append(_assemble(extracted, schema, anchor_node=node))

    return etl_paths


# --- private helpers ---

def _build_wire_map(nodes: list[dict]) -> dict[str, list[str]]:
    wire_map: dict[str, list[str]] = {}
    for node in nodes:
        targets = [t for port in node.get("wires", []) for t in port]
        if targets:
            wire_map[node["id"]] = targets
    return wire_map


def _build_reverse_wire_map(nodes: list[dict]) -> dict[str, list[str]]:
    reverse: dict[str, list[str]] = {}
    for node in nodes:
        for port in node.get("wires", []):
            for target_id in port:
                reverse.setdefault(target_id, []).append(node["id"])
    return reverse


def _walk_to_start(
    node: dict,
    reverse_wire_map: dict[str, list[str]],
    node_map: dict[str, dict],
) -> dict:
    current = node
    while True:
        predecessors = reverse_wire_map.get(current["id"], [])
        if not predecessors:
            return current
        current = node_map[predecessors[0]]


def _assemble(
    extracted: dict[str, Any],
    schema: ProtocolSchema,
    anchor_node: dict,
) -> ETLPath:
    return ETLPath(
        extract=ExtractSpec(
            protocol=schema.protocol,
            endpoint=extracted.get("extract.endpoint", ""),
            href=extracted.get("extract.href", ""),
            control_packet=extracted.get("extract.control_packet"),
        ),
        transform=TransformSpec(
            function_code=extracted.get("transform.function_code", "return msg;"),
        ),
        load=LoadSpec(
            sink_url=extracted.get("load.sink_url", ""),
        ),
        nodered=NodeRedAnchor(
            endpoint_node_id=anchor_node["id"],
            config_node_id=extracted.get("nodered.config_node_id"),
            node_ids=extracted.get("nodered.node_ids", {}),
        ),
    )
