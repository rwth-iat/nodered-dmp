import pytest

from nodered_dmp.model.etl_path import ETLPath, ExtractSpec, LoadSpec, NodeRedAnchor, TransformSpec
from nodered_dmp.nodered.visual import apply_visual_overrides


def _make_chain(prefix: str, count: int, x_start: int = 100) -> list[dict]:
    """Build a linear chain of `count` nodes wired in order."""
    nodes = [
        {"id": f"{prefix}_{i}", "type": f"type_{i}", "x": x_start + i * 200, "y": 300, "wires": [], "name": ""}
        for i in range(count)
    ]
    for i in range(count - 1):
        nodes[i]["wires"] = [[nodes[i + 1]["id"]]]
    return nodes


def _make_etl_path(etl_path_id: str, endpoint_node_id: str) -> ETLPath:
    return ETLPath(
        etl_path_id=etl_path_id,
        extract=ExtractSpec(protocol="mqtt", endpoint="mqtt://localhost", href="/test"),
        transform=TransformSpec(),
        load=LoadSpec(sink_url="http://localhost/prop"),
        nodered=NodeRedAnchor(endpoint_node_id=endpoint_node_id),
    )


def test_positions_copied():
    old_chain = _make_chain("old", 3, x_start=50)
    old_chain[0]["x"] = 50
    old_chain[1]["x"] = 250
    old_chain[2]["x"] = 450

    new_chain = _make_chain("new", 3, x_start=170)

    etl = _make_etl_path("p1", "new_0")  # anchor is new_0 (chain start for MQTT)
    old_anchors = {"p1": "old_0"}

    result = apply_visual_overrides(old_chain, new_chain, old_anchors, [etl])

    result_map = {n["id"]: n for n in result}
    assert result_map["new_0"]["x"] == 50
    assert result_map["new_1"]["x"] == 250
    assert result_map["new_2"]["x"] == 450


def test_name_copied():
    old_chain = _make_chain("old", 2)
    old_chain[1]["name"] = "My Sensor"

    new_chain = _make_chain("new", 2)

    etl = _make_etl_path("p1", "new_0")
    old_anchors = {"p1": "old_0"}

    result = apply_visual_overrides(old_chain, new_chain, old_anchors, [etl])
    result_map = {n["id"]: n for n in result}
    assert result_map["new_1"]["name"] == "My Sensor"


def test_color_copied():
    old_chain = _make_chain("old", 2)
    old_chain[0]["color"] = "#aabbcc"

    new_chain = _make_chain("new", 2)

    etl = _make_etl_path("p1", "new_0")
    old_anchors = {"p1": "old_0"}

    result = apply_visual_overrides(old_chain, new_chain, old_anchors, [etl])
    result_map = {n["id"]: n for n in result}
    assert result_map["new_0"]["color"] == "#aabbcc"


def test_structural_fields_not_overwritten():
    old_chain = _make_chain("old", 2)
    old_chain[0]["type"] = "old_type"

    new_chain = _make_chain("new", 2)
    new_chain[0]["type"] = "new_type"

    etl = _make_etl_path("p1", "new_0")
    old_anchors = {"p1": "old_0"}

    result = apply_visual_overrides(old_chain, new_chain, old_anchors, [etl])
    result_map = {n["id"]: n for n in result}
    assert result_map["new_0"]["type"] == "new_type"


def test_missing_old_anchor_leaves_new_nodes_unchanged():
    old_chain = _make_chain("old", 2)
    old_chain[0]["x"] = 999

    new_chain = _make_chain("new", 2)
    new_chain[0]["x"] = 170

    etl = _make_etl_path("p1", "new_0")
    old_anchors = {}  # no old anchor for this path

    result = apply_visual_overrides(old_chain, new_chain, old_anchors, [etl])
    result_map = {n["id"]: n for n in result}
    assert result_map["new_0"]["x"] == 170


def test_no_nodered_anchor_skipped():
    old_chain = _make_chain("old", 2)
    new_chain = _make_chain("new", 2)
    new_chain[0]["x"] = 170

    etl = ETLPath(
        etl_path_id="p1",
        extract=ExtractSpec(protocol="mqtt", endpoint="mqtt://localhost", href="/test"),
        transform=TransformSpec(),
        load=LoadSpec(sink_url="http://localhost/prop"),
        nodered=None,
    )
    old_anchors = {"p1": "old_0"}

    result = apply_visual_overrides(old_chain, new_chain, old_anchors, [etl])
    result_map = {n["id"]: n for n in result}
    assert result_map["new_0"]["x"] == 170


def test_anchor_mid_chain_walks_back_to_start():
    """Anchor at index 1 (like OPC UA OpcUa-Item); chain has 3 nodes total."""
    old_chain = _make_chain("old", 3)
    old_chain[0]["x"] = 10
    old_chain[1]["x"] = 20
    old_chain[2]["x"] = 30

    new_chain = _make_chain("new", 3)

    # anchor is index 1 in both chains
    etl = _make_etl_path("p1", "new_1")
    old_anchors = {"p1": "old_1"}

    result = apply_visual_overrides(old_chain, new_chain, old_anchors, [etl])
    result_map = {n["id"]: n for n in result}
    assert result_map["new_0"]["x"] == 10
    assert result_map["new_1"]["x"] == 20
    assert result_map["new_2"]["x"] == 30


def test_multiple_etl_paths():
    old_chain_a = _make_chain("old_a", 2)
    old_chain_a[0]["x"] = 50

    old_chain_b = _make_chain("old_b", 2)
    old_chain_b[0]["x"] = 900

    new_chain_a = _make_chain("new_a", 2)
    new_chain_b = _make_chain("new_b", 2)

    etl_a = _make_etl_path("a", "new_a_0")
    etl_b = _make_etl_path("b", "new_b_0")
    old_anchors = {"a": "old_a_0", "b": "old_b_0"}

    result = apply_visual_overrides(
        old_chain_a + old_chain_b,
        new_chain_a + new_chain_b,
        old_anchors,
        [etl_a, etl_b],
    )
    result_map = {n["id"]: n for n in result}
    assert result_map["new_a_0"]["x"] == 50
    assert result_map["new_b_0"]["x"] == 900
