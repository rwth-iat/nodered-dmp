from nodered_dmp.model.etl_path import ETLPath

_VISUAL_FIELDS = ("x", "y", "name", "color", "l")


def apply_visual_overrides(
    old_nodes: list[dict],
    new_nodes: list[dict],
    old_anchors: dict[str, str],
    etl_paths: list[ETLPath],
) -> list[dict]:
    """
    Copy visual-only properties (x, y, name, color) from each old chain to the
    corresponding new chain, matched by ETLPath identity and slot position.

    old_anchors maps etl_path_id → endpoint_node_id in the old flow.
    etl_paths must already have updated nodered anchors (i.e. after build_flow).
    """
    old_map = {n["id"]: n for n in old_nodes}
    old_wire_map = _build_wire_map(old_nodes)
    old_reverse = _build_reverse_wire_map(old_nodes)

    new_map = {n["id"]: n for n in new_nodes}
    new_wire_map = _build_wire_map(new_nodes)
    new_reverse = _build_reverse_wire_map(new_nodes)

    result = [dict(n) for n in new_nodes]
    result_by_id = {n["id"]: n for n in result}

    for etl_path in etl_paths:
        if etl_path.nodered is None:
            continue
        old_anchor_id = old_anchors.get(etl_path.etl_path_id)
        if old_anchor_id is None:
            continue

        old_chain = _walk_chain(old_anchor_id, old_map, old_wire_map, old_reverse)
        new_chain = _walk_chain(
            etl_path.nodered.endpoint_node_id, new_map, new_wire_map, new_reverse
        )

        for old_node, new_node in zip(old_chain, new_chain):
            target = result_by_id.get(new_node["id"])
            if target is None:
                continue
            for field in _VISUAL_FIELDS:
                if field in old_node:
                    target[field] = old_node[field]

    return result


def _walk_chain(
    anchor_id: str,
    node_map: dict,
    wire_map: dict,
    reverse_wire_map: dict,
) -> list[dict]:
    """Walk backward from anchor to chain start, then forward to collect all chain nodes."""
    anchor = node_map.get(anchor_id)
    if anchor is None:
        return []

    current = anchor
    while True:
        preds = reverse_wire_map.get(current["id"], [])
        if not preds:
            break
        pred = node_map.get(preds[0])
        if pred is None or pred.get("type") == "tab":
            break
        current = pred

    chain: list[dict] = []
    visited: set[str] = set()
    while current is not None:
        if current["id"] in visited:
            break
        visited.add(current["id"])
        chain.append(current)
        nexts = wire_map.get(current["id"], [])
        if not nexts:
            break
        current = node_map.get(nexts[0])

    return chain


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
