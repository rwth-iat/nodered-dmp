import json
from pathlib import Path

import nodered_flowgen as nr
import pytest

from nodered_dmp.model.etl_path import ETLPath, ExtractSpec, LoadSpec, TransformSpec
from nodered_dmp.protocols.base import InvalidETLPathError, build_chain, parse_chain
from nodered_dmp.protocols import mqtt, opcua

ARTIFACTS = Path(__file__).parent / "artifacts"


# --- helpers ---

def make_etl_path(**overrides) -> ETLPath:
    defaults = dict(
        extract=ExtractSpec(
            protocol="mqtt",
            endpoint="mqtt://localhost:1883",
            href="/device/voltage",
        ),
        transform=TransformSpec(),
        load=LoadSpec(
            sink_url="http://localhost:8081/submodels/abc/submodel-elements/voltage",
        ),
    )
    defaults.update(overrides)
    return ETLPath(**defaults)


def make_flow_and_subflow(extra_columns: int = 0):
    base_columns = [170, 470, 770, 1070, 1270]
    extra = [base_columns[-1] + 200 * i for i in range(1, extra_columns + 1)]
    flow = nr.Flow(
        "Test Flow",
        columns=base_columns + extra,
        x_offset=0,
        y_offset=140,
        vertical_spacing=80,
    )
    subflow = nr.Subflow(name="AASInterface", columns=[120, 320], x_offset=200, y_offset=140)
    get_prop = nr.HTTPRequest(name="get property")
    subflow.add_node(get_prop, column=0)
    put_prop = nr.HTTPRequest(method="PUT", name="write property")
    subflow.add_node(put_prop, column=1)
    subflow.connect_to_input(get_prop)
    subflow.connect_nodes(get_prop, put_prop)
    flow.add_subflow(subflow)
    return flow, subflow


def load_flow_json(filename: str) -> list[dict]:
    return json.loads((ARTIFACTS / filename).read_text())


def build_maps(nodes: list[dict]) -> tuple[dict, dict]:
    node_map = {n["id"]: n for n in nodes}
    wire_map = {
        n["id"]: n["wires"][0]
        for n in nodes
        if n.get("wires") and n["wires"][0]
    }
    return node_map, wire_map


# --- build_chain tests (MQTT) ---

@pytest.fixture
def built_mqtt():
    etl_path = make_etl_path()
    flow, subflow = make_flow_and_subflow()
    build_chain(mqtt.SCHEMA, flow, subflow, etl_path)
    nodes = json.loads(flow.generate_json())
    return nodes, etl_path


def test_build_chain_creates_mqtt_broker(built_mqtt):
    nodes, _ = built_mqtt
    brokers = [n for n in nodes if n["type"] == "mqtt-broker"]
    assert len(brokers) == 1
    assert brokers[0]["broker"] == "localhost"
    assert brokers[0]["port"] == 1883


def test_build_chain_creates_mqtt_in_with_topic(built_mqtt):
    nodes, _ = built_mqtt
    mqtt_in = next(n for n in nodes if n["type"] == "mqtt in")
    assert mqtt_in["topic"] == "/device/voltage"


def test_build_chain_creates_pre_change(built_mqtt):
    nodes, _ = built_mqtt
    # find the change node that moves payload → updateValue
    change_nodes = [n for n in nodes if n["type"] == "change" and n.get("z") != next(
        n["id"] for n in nodes if n["type"] == "subflow"
    )]
    pre_change = next(
        n for n in change_nodes
        if any(r.get("to") == "updateValue" for r in n.get("rules", []))
    )
    assert pre_change is not None


def test_build_chain_creates_function_with_code(built_mqtt):
    nodes, _ = built_mqtt
    fn = next(n for n in nodes if n["type"] == "function")
    assert fn["func"] == "return msg;"


def test_build_chain_creates_url_setter_change(built_mqtt):
    nodes, _ = built_mqtt
    url_setter = next(
        n for n in nodes
        if n["type"] == "change" and any(
            r.get("p") == "url" for r in n.get("rules", [])
        )
    )
    assert url_setter["rules"][0]["to"] == "http://localhost:8081/submodels/abc/submodel-elements/voltage"


def test_build_chain_creates_subflow_instance(built_mqtt):
    nodes, _ = built_mqtt
    subflow_def = next(n for n in nodes if n["type"] == "subflow")
    instances = [n for n in nodes if n["type"] == f"subflow:{subflow_def['id']}"]
    assert len(instances) == 1


def test_build_chain_populates_nodered_anchor(built_mqtt):
    nodes, etl_path = built_mqtt
    assert etl_path.nodered is not None
    assert etl_path.nodered.endpoint_node_id is not None
    assert etl_path.nodered.config_node_id is not None


def test_build_chain_endpoint_node_id_matches_mqtt_in(built_mqtt):
    nodes, etl_path = built_mqtt
    mqtt_in = next(n for n in nodes if n["type"] == "mqtt in")
    assert etl_path.nodered.endpoint_node_id == mqtt_in["id"]


def test_build_chain_config_node_id_matches_broker(built_mqtt):
    nodes, etl_path = built_mqtt
    broker = next(n for n in nodes if n["type"] == "mqtt-broker")
    assert etl_path.nodered.config_node_id == broker["id"]


def test_build_chain_column_positions(built_mqtt):
    _, etl_path = built_mqtt
    positions = etl_path.nodered.column_positions
    assert positions["endpoint"] == 0
    assert positions["pre_change"] == 1
    assert positions["transform"] == 2
    assert positions["url_setter"] == 3
    assert positions["sink"] == 4


def test_build_chain_reuses_config_node():
    """Two ETLPaths on the same broker share a single config node."""
    flow, subflow = make_flow_and_subflow()
    etl1 = make_etl_path(aimc_idshort_path="Relations.voltage")
    etl2 = make_etl_path(
        aimc_idshort_path="Relations.status",
        extract=ExtractSpec(protocol="mqtt", endpoint="mqtt://localhost:1883", href="/device/status"),
        load=LoadSpec(sink_url="http://localhost:8081/submodels/abc/submodel-elements/status"),
    )

    # Build config node once, reuse for both
    config_node = mqtt.SCHEMA.config.builds(etl1)
    flow.add_node(config_node)
    build_chain(mqtt.SCHEMA, flow, subflow, etl1, config_node=config_node)
    build_chain(mqtt.SCHEMA, flow, subflow, etl2, config_node=config_node)

    nodes = json.loads(flow.generate_json())
    brokers = [n for n in nodes if n["type"] == "mqtt-broker"]
    assert len(brokers) == 1
    mqtt_ins = [n for n in nodes if n["type"] == "mqtt in"]
    assert len(mqtt_ins) == 2


# --- parse_chain tests (MQTT) ---

@pytest.fixture
def mqtt_flow_nodes():
    """Load the artifact generated by the existing test suite."""
    return load_flow_json("flow_mqtt.json")


def test_parse_chain_extracts_href(mqtt_flow_nodes):
    node_map, wire_map = build_maps(mqtt_flow_nodes)
    start = next(n for n in mqtt_flow_nodes if n["type"] == "mqtt in")
    result = parse_chain(mqtt.SCHEMA, start, node_map, wire_map)
    assert result["extract.href"] == "/sampleDevice/properties/voltage"


def test_parse_chain_extracts_endpoint(mqtt_flow_nodes):
    node_map, wire_map = build_maps(mqtt_flow_nodes)
    start = next(n for n in mqtt_flow_nodes if n["type"] == "mqtt in")
    result = parse_chain(mqtt.SCHEMA, start, node_map, wire_map)
    assert result["extract.endpoint"] == "mqtt://localhost:1883"


def test_parse_chain_extracts_function_code(mqtt_flow_nodes):
    node_map, wire_map = build_maps(mqtt_flow_nodes)
    start = next(n for n in mqtt_flow_nodes if n["type"] == "mqtt in")
    result = parse_chain(mqtt.SCHEMA, start, node_map, wire_map)
    assert result["transform.function_code"] == "return msg;"


def test_parse_chain_extracts_sink_url(mqtt_flow_nodes):
    node_map, wire_map = build_maps(mqtt_flow_nodes)
    start = next(n for n in mqtt_flow_nodes if n["type"] == "mqtt in")
    result = parse_chain(mqtt.SCHEMA, start, node_map, wire_map)
    assert "submodel-elements" in result["load.sink_url"]
    assert result["load.sink_url"].startswith("http://")


def test_parse_chain_works_for_all_mqtt_in_nodes(mqtt_flow_nodes):
    node_map, wire_map = build_maps(mqtt_flow_nodes)
    mqtt_ins = [n for n in mqtt_flow_nodes if n["type"] == "mqtt in"]
    assert len(mqtt_ins) == 2
    for start in mqtt_ins:
        result = parse_chain(mqtt.SCHEMA, start, node_map, wire_map)
        assert "extract.href" in result
        assert "load.sink_url" in result


# --- round-trip test ---

def test_build_then_parse_recovers_etl_fields():
    """Build a flow from an ETLPath, parse it back, verify fields match."""
    original = make_etl_path(
        extract=ExtractSpec(
            protocol="mqtt",
            endpoint="mqtt://broker.example.com:1883",
            href="/sensors/temperature",
        ),
        transform=TransformSpec(function_code="msg.payload = msg.payload * 1.8 + 32; return msg;"),
        load=LoadSpec(sink_url="http://aas.example.com/submodels/abc/submodel-elements/temperature"),
    )

    flow, subflow = make_flow_and_subflow()
    build_chain(mqtt.SCHEMA, flow, subflow, original)

    nodes = json.loads(flow.generate_json())
    node_map, wire_map = build_maps(nodes)

    start = next(n for n in nodes if n["type"] == "mqtt in")
    extracted = parse_chain(mqtt.SCHEMA, start, node_map, wire_map)

    assert extracted["extract.href"] == original.extract.href
    assert extracted["extract.endpoint"] == original.extract.endpoint
    assert extracted["transform.function_code"] == original.transform.function_code
    assert extracted["load.sink_url"] == original.load.sink_url


def test_round_trip_default_function_code():
    original = make_etl_path()  # default "return msg;"
    flow, subflow = make_flow_and_subflow()
    build_chain(mqtt.SCHEMA, flow, subflow, original)

    nodes = json.loads(flow.generate_json())
    node_map, wire_map = build_maps(nodes)
    start = next(n for n in nodes if n["type"] == "mqtt in")
    extracted = parse_chain(mqtt.SCHEMA, start, node_map, wire_map)

    assert extracted["transform.function_code"] == "return msg;"


def test_round_trip_multiple_etl_paths():
    """Two ETLPaths sharing a broker both survive the round-trip."""
    flow, subflow = make_flow_and_subflow()

    etl1 = make_etl_path(
        aimc_idshort_path="Relations.voltage",
        extract=ExtractSpec(protocol="mqtt", endpoint="mqtt://localhost:1883", href="/device/voltage"),
        load=LoadSpec(sink_url="http://localhost:8081/submodels/abc/submodel-elements/voltage"),
    )
    etl2 = make_etl_path(
        aimc_idshort_path="Relations.temperature",
        extract=ExtractSpec(protocol="mqtt", endpoint="mqtt://localhost:1883", href="/device/temperature"),
        transform=TransformSpec(function_code="msg.payload = msg.payload - 273.15; return msg;"),
        load=LoadSpec(sink_url="http://localhost:8081/submodels/abc/submodel-elements/temperature"),
    )

    config_node = mqtt.SCHEMA.config.builds(etl1)
    flow.add_node(config_node)
    build_chain(mqtt.SCHEMA, flow, subflow, etl1, config_node=config_node)
    build_chain(mqtt.SCHEMA, flow, subflow, etl2, config_node=config_node)

    nodes = json.loads(flow.generate_json())
    node_map, wire_map = build_maps(nodes)

    mqtt_ins = [n for n in nodes if n["type"] == "mqtt in"]
    assert len(mqtt_ins) == 2

    results = {
        parsed["extract.href"]: parsed
        for n in mqtt_ins
        for parsed in [parse_chain(mqtt.SCHEMA, n, node_map, wire_map)]
    }

    assert results["/device/voltage"]["load.sink_url"] == etl1.load.sink_url
    assert results["/device/temperature"]["transform.function_code"] == etl2.transform.function_code


# --- build_chain tests (OPC UA) ---

def make_opcua_etl_path(**overrides) -> ETLPath:
    defaults = dict(
        extract=ExtractSpec(
            protocol="opcua",
            endpoint="opc.tcp://localhost:4840",
            href="ns=2;s=Device/Pressure",
        ),
        transform=TransformSpec(),
        load=LoadSpec(
            sink_url="http://localhost:8081/submodels/abc/submodel-elements/pressure",
        ),
    )
    defaults.update(overrides)
    return ETLPath(**defaults)


@pytest.fixture
def built_opcua():
    etl_path = make_opcua_etl_path()
    flow, subflow = make_flow_and_subflow(extra_columns=2)
    build_chain(opcua.SCHEMA, flow, subflow, etl_path)
    nodes = json.loads(flow.generate_json())
    return nodes, etl_path


def test_build_chain_opcua_creates_endpoint_config(built_opcua):
    nodes, _ = built_opcua
    endpoints = [n for n in nodes if n["type"] == "OpcUa-Endpoint"]
    assert len(endpoints) == 1
    assert endpoints[0]["endpoint"] == "opc.tcp://localhost:4840"


def test_build_chain_opcua_creates_item_with_node_id(built_opcua):
    nodes, _ = built_opcua
    item = next(n for n in nodes if n["type"] == "OpcUa-Item")
    assert item["item"] == "ns=2;s=Device/Pressure"


def test_build_chain_opcua_creates_inject_node(built_opcua):
    nodes, _ = built_opcua
    inject_nodes = [n for n in nodes if n["type"] == "inject"]
    assert len(inject_nodes) == 1
    assert inject_nodes[0]["repeat"] == "1"


def test_build_chain_opcua_creates_client_in_read_mode(built_opcua):
    nodes, _ = built_opcua
    client = next(n for n in nodes if n["type"] == "OpcUa-Client")
    assert client["action"] == "read"


def test_build_chain_opcua_client_references_endpoint(built_opcua):
    nodes, _ = built_opcua
    endpoint = next(n for n in nodes if n["type"] == "OpcUa-Endpoint")
    client = next(n for n in nodes if n["type"] == "OpcUa-Client")
    assert client["endpoint"] == endpoint["id"]


def test_build_chain_opcua_creates_function_node(built_opcua):
    nodes, _ = built_opcua
    fn = next(n for n in nodes if n["type"] == "function")
    assert fn["func"] == "return msg;"


def test_build_chain_opcua_populates_nodered_anchor(built_opcua):
    nodes, etl_path = built_opcua
    assert etl_path.nodered is not None
    item = next(n for n in nodes if n["type"] == "OpcUa-Item")
    endpoint = next(n for n in nodes if n["type"] == "OpcUa-Endpoint")
    assert etl_path.nodered.endpoint_node_id == item["id"]
    assert etl_path.nodered.config_node_id == endpoint["id"]


def test_build_chain_opcua_column_positions(built_opcua):
    _, etl_path = built_opcua
    positions = etl_path.nodered.column_positions
    assert positions["trigger"] == 0
    assert positions["endpoint"] == 1   # OpcUa-Item
    assert positions["client"] == 2
    assert positions["transform"] == 4
    assert positions["sink"] == 6


# --- round-trip test (OPC UA) ---

def test_opcua_round_trip_recovers_etl_fields():
    original = make_opcua_etl_path(
        extract=ExtractSpec(
            protocol="opcua",
            endpoint="opc.tcp://sensor-gw:4840",
            href="ns=3;s=Temperature",
        ),
        transform=TransformSpec(function_code="msg.payload = msg.payload - 273.15; return msg;"),
        load=LoadSpec(sink_url="http://aas/submodels/abc/submodel-elements/temperature"),
    )

    flow, subflow = make_flow_and_subflow(extra_columns=2)
    build_chain(opcua.SCHEMA, flow, subflow, original)
    nodes = json.loads(flow.generate_json())
    node_map, wire_map = build_maps(nodes)

    # anchor is OpcUa-Item; parse_chain walks back to the Inject (chain start)
    inject = next(n for n in nodes if n["type"] == "inject")
    extracted = parse_chain(opcua.SCHEMA, inject, node_map, wire_map)

    assert extracted["extract.href"] == original.extract.href
    assert extracted["extract.endpoint"] == original.extract.endpoint
    assert extracted["transform.function_code"] == original.transform.function_code
    assert extracted["load.sink_url"] == original.load.sink_url


# --- parse_chain error tests ---

def test_parse_chain_raises_on_wrong_node_type(mqtt_flow_nodes):
    node_map, wire_map = build_maps(mqtt_flow_nodes)
    # Use a change node as the start (wrong type for 'endpoint' slot)
    wrong_start = next(n for n in mqtt_flow_nodes if n["type"] == "change")
    with pytest.raises(InvalidETLPathError, match="expected 'mqtt in'"):
        parse_chain(mqtt.SCHEMA, wrong_start, node_map, wire_map)


def test_parse_chain_raises_on_broken_wire(mqtt_flow_nodes):
    node_map, wire_map = build_maps(mqtt_flow_nodes)
    start = next(n for n in mqtt_flow_nodes if n["type"] == "mqtt in")
    # Remove the wire from the start node so the chain is broken
    broken_wire_map = {k: v for k, v in wire_map.items() if k != start["id"]}
    with pytest.raises(InvalidETLPathError, match="no outgoing wire"):
        parse_chain(mqtt.SCHEMA, start, node_map, broken_wire_map)


def test_parse_chain_raises_on_missing_config_node(mqtt_flow_nodes):
    node_map, wire_map = build_maps(mqtt_flow_nodes)
    start = next(n for n in mqtt_flow_nodes if n["type"] == "mqtt in")
    # Remove the broker from node_map
    broker_id = start["broker"]
    incomplete_node_map = {k: v for k, v in node_map.items() if k != broker_id}
    with pytest.raises(InvalidETLPathError, match="config node"):
        parse_chain(mqtt.SCHEMA, start, incomplete_node_map, wire_map)
