import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from nodered_dmp.aas.aas_to_etlpath import parse_aimc
from nodered_dmp.flow_builder import build_flow

FIXTURES = Path(__file__).parent / "fixtures"
ARTIFACTS = Path(__file__).parent / "artifacts"
SERVER = "http://localhost:8081"
AIMC_URL = SERVER + "/submodels/abc"

# Mock call order mirrors parse_aimc traversal:
#   1. AIMC submodel
#   2. InterfaceHTTP  (protocol "http" → skipped by _KNOWN_PROTOCOLS)
#   3. InterfaceMODBUS (protocol "modbus+tcp" → skipped)
#   4. InterfaceMQTT  (protocol "mqtt" → process)
#   5. MQTT voltage property
#   6. MQTT status property
FIXTURE_SEQUENCE = [
    "AssetInterfacesMappingConfiguration.json",
    "AssetInterfacesDescription__InterfaceHTTP.json",
    "AssetInterfacesDescription__InterfaceMODBUS.json",
    "AssetInterfacesDescription__InterfaceMQTT.json",
    "AssetInterfacesDescription__InterfaceMQTT_InterfaceMetadata_Properties_voltage.json",
    "AssetInterfacesDescription__InterfaceMQTT_InterfaceMetadata_Properties_status.json",
]


def _mock(name: str) -> Mock:
    m = Mock()
    m.json.return_value = json.loads((FIXTURES / name).read_text())
    return m


@pytest.fixture
def built_flow():
    mocks = [_mock(f) for f in FIXTURE_SEQUENCE]
    with patch("nodered_dmp.aas.client.requests.get", side_effect=mocks):
        etl_paths = parse_aimc(AIMC_URL, SERVER)
    flow = build_flow(etl_paths)
    nodes = json.loads(flow.generate_json())
    ARTIFACTS.mkdir(exist_ok=True)
    (ARTIFACTS / "flow_mqtt.json").write_text(json.dumps(nodes, indent=2))
    return nodes


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
    mqtt_in_nodes = [n for n in built_flow if n["type"] == "mqtt in"]
    assert len(mqtt_in_nodes) == 2


def test_flow_builder_aas_interface_subflow_instanced(built_flow):
    subflow_def = next(n for n in built_flow if n["type"] == "subflow")
    instances = [n for n in built_flow if n["type"].startswith("subflow:")]
    assert all(n["type"] == f"subflow:{subflow_def['id']}" for n in instances)
    assert len(instances) == 2


def test_flow_tab_label_is_aimc_submodel_id(built_flow):
    tab = next(n for n in built_flow if n["type"] == "tab")
    assert "AssetInterfacesMappingConfiguration" in tab["label"]
