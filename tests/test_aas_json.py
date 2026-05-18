import base64
import json
import runpy
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

import nodered_dmp.aas_json as mod

FIXTURES = Path(__file__).parent / "fixtures"
SERVER = "http://localhost:8081"


def fixture(name):
    m = Mock()
    m.json.return_value = json.loads((FIXTURES / name).read_text())
    return m


# --- Pure functions (no HTTP) ---

def test_id_to_url():
    url = mod.id_to_url("http://server:8081", "https://example.com/ids/sm/Test")
    b64 = base64.b64encode(b"https://example.com/ids/sm/Test").decode()
    assert url == f"http://server:8081/submodels/{b64}"


def test_get_host_and_port_mqtt():
    scheme, host, port = mod.get_host_and_port("mqtt://localhost:1883")
    assert scheme == "mqtt"
    assert host == "localhost"
    assert port == 1883


def test_get_host_and_port_http():
    scheme, host, port = mod.get_host_and_port("http://localhost:8083")
    assert scheme == "http"
    assert host == "localhost"
    assert port == 8083


def test_resolve_relationship_to_reference():
    keys = [
        {"type": "Submodel", "value": "https://example.com/ids/sm/AssetInterfacesDescription"},
        {"type": "SubmodelElementCollection", "value": "InterfaceMQTT"},
        {"type": "Property", "value": "voltage"},
    ]
    b64 = base64.b64encode(b"https://example.com/ids/sm/AssetInterfacesDescription").decode()
    result = mod.resolve_relationship_to_reference(keys)
    assert result == f"/submodels/{b64}/submodel-elements/InterfaceMQTT.voltage"


def test_resolve_relationship_to_reference_raises_if_not_submodel():
    keys = [{"type": "Property", "value": "something"}]
    with pytest.raises(Exception):
        mod.resolve_relationship_to_reference(keys)


# --- Functions with HTTP calls ---

def test_get_connections_returns_three_interfaces():
    with patch.object(mod.requests, "get", return_value=fixture("AssetInterfacesMappingConfiguration.json")):
        connections = mod.get_connections(SERVER + "/submodels/abc")
    assert len(connections) == 3


def test_get_connections_interface_paths():
    with patch.object(mod.requests, "get", return_value=fixture("AssetInterfacesMappingConfiguration.json")):
        connections = mod.get_connections(SERVER + "/submodels/abc")
    interfaces = [c["interface"] for c in connections]
    assert any("InterfaceHTTP" in i for i in interfaces)
    assert any("InterfaceMODBUS" in i for i in interfaces)
    assert any("InterfaceMQTT" in i for i in interfaces)


def test_get_connections_source_sink_pairs():
    with patch.object(mod.requests, "get", return_value=fixture("AssetInterfacesMappingConfiguration.json")):
        connections = mod.get_connections(SERVER + "/submodels/abc")
    for conn in connections:
        assert "source_sink" in conn
        assert len(conn["source_sink"]) == 2  # voltage + status for each interface


def test_get_endpoint_metadata_mqtt():
    with patch.object(mod.requests, "get", return_value=fixture("AssetInterfacesDescription__InterfaceMQTT.json")):
        result = mod.get_EndpointMetadata(SERVER + "/some/path")
    assert result == "mqtt://localhost:1883"


def test_get_endpoint_metadata_http():
    with patch.object(mod.requests, "get", return_value=fixture("AssetInterfacesDescription__InterfaceHTTP.json")):
        result = mod.get_EndpointMetadata(SERVER + "/some/path")
    assert result == "http://localhost:8083"


def test_get_endpoint_metadata_modbus():
    with patch.object(mod.requests, "get", return_value=fixture("AssetInterfacesDescription__InterfaceMODBUS.json")):
        result = mod.get_EndpointMetadata(SERVER + "/some/path")
    assert result == "modbus+tcp://192.168.0.1:502/1"


def test_get_interface_metadata_voltage():
    with patch.object(mod.requests, "get", return_value=fixture("AssetInterfacesDescription__InterfaceMQTT_InterfaceMetadata_Properties_voltage.json")):
        result = mod.get_InterfaceMetadata(SERVER + "/some/path")
    assert result == "/sampleDevice/properties/voltage"


def test_get_interface_metadata_status():
    with patch.object(mod.requests, "get", return_value=fixture("AssetInterfacesDescription__InterfaceMQTT_InterfaceMetadata_Properties_status.json")):
        result = mod.get_InterfaceMetadata(SERVER + "/some/path")
    assert result == "/sampleDevice/properties/status"


# --- Flow builder (__main__) ---

FLOW_BUILDER_FIXTURES = [
    "AssetInterfacesMappingConfiguration.json",
    "AssetInterfacesDescription__InterfaceHTTP.json",
    "AssetInterfacesDescription__InterfaceMODBUS.json",
    "AssetInterfacesDescription__InterfaceMQTT.json",
    "AssetInterfacesDescription__InterfaceMQTT_InterfaceMetadata_Properties_voltage.json",
    "AssetInterfacesDescription__InterfaceMQTT_InterfaceMetadata_Properties_status.json",
]


ARTIFACTS = Path(__file__).parent / "artifacts"


@pytest.fixture
def built_flow():
    mocks = [fixture(f) for f in FLOW_BUILDER_FIXTURES]
    captured = StringIO()
    with patch("requests.get", side_effect=mocks):
        with patch("sys.stdout", captured):
            runpy.run_path("nodered_dmp/aas_json.py", run_name="__main__")
    flow = json.loads(captured.getvalue())
    ARTIFACTS.mkdir(exist_ok=True)
    (ARTIFACTS / "flow.json").write_text(json.dumps(flow, indent=2))
    return flow


def test_flow_builder_node_count(built_flow):
    assert len(built_flow) == 17


def test_flow_builder_has_tab_and_subflow(built_flow):
    types = [n["type"] for n in built_flow]
    assert "tab" in types
    assert "subflow" in types


def test_flow_builder_mqtt_broker(built_flow):
    broker = next(n for n in built_flow if n["type"] == "mqtt-broker")
    assert broker["broker"] == "localhost"
    assert broker["port"] == 1883


def test_flow_builder_mqtt_in_topics(built_flow):
    topics = [n["topic"] for n in built_flow if n["type"] == "mqtt in"]
    assert "/sampleDevice/properties/voltage" in topics
    assert "/sampleDevice/properties/status" in topics


def test_flow_builder_only_mqtt_connections_processed(built_flow):
    # HTTP and MODBUS interfaces must not produce mqtt in nodes
    mqtt_in_nodes = [n for n in built_flow if n["type"] == "mqtt in"]
    assert len(mqtt_in_nodes) == 2


def test_flow_builder_aas_interface_subflow_instanced(built_flow):
    subflow_def = next(n for n in built_flow if n["type"] == "subflow")
    instances = [n for n in built_flow if n["type"].startswith("subflow:")]
    assert all(n["type"] == f"subflow:{subflow_def['id']}" for n in instances)
    assert len(instances) == 2
