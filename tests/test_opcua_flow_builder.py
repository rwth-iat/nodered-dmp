import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from nodered_dmp.aimc_parser import get_connections
from nodered_dmp.flow_builder import build_flow

FIXTURES = Path(__file__).parent / "fixtures"
ARTIFACTS = Path(__file__).parent / "artifacts"
SERVER = "http://localhost:8081"

AIMC_FIXTURE = "AssetInterfacesMappingConfiguration__TU10_F17.json"
ENDPOINT_FIXTURES = [
    "AssetInterfacesDescription__TU10_F17__InterfaceOPCUA.json",
]
PROPERTY_FIXTURES = [
    "AssetInterfacesDescription__TU10_F17__InterfaceOPCUA_properties_CurrentValue.json",
]


def fixture(name):
    m = Mock()
    m.json.return_value = json.loads((FIXTURES / name).read_text())
    return m


@pytest.fixture
def built_flow():
    all_fixtures = [AIMC_FIXTURE] + ENDPOINT_FIXTURES + PROPERTY_FIXTURES
    mocks = [fixture(f) for f in all_fixtures]
    with patch("nodered_dmp.aas_client.requests.get", side_effect=mocks):
        connections = get_connections(SERVER + "/submodels/abc")
        flow = build_flow(connections, SERVER)
    nodes = json.loads(flow.generate_json())
    ARTIFACTS.mkdir(exist_ok=True)
    (ARTIFACTS / "flow_opcua.json").write_text(json.dumps(nodes, indent=2))
    return nodes


def test_opcua_flow_has_tab_and_subflow(built_flow):
    types = [n["type"] for n in built_flow]
    assert "tab" in types
    assert "subflow" in types


def test_opcua_flow_has_endpoint(built_flow):
    endpoint = next(n for n in built_flow if n["type"] == "OpcUa-Endpoint")
    assert endpoint["endpoint"] == "opc.tcp://localhost:9409/DvOpcUaServer"


def test_opcua_flow_has_inject(built_flow):
    inject = next(n for n in built_flow if n["type"] == "inject")
    assert inject["repeat"] == "0.5"
    assert inject["payloadType"] == "bool"


def test_opcua_flow_has_item_with_node_id(built_flow):
    item = next(n for n in built_flow if n["type"] == "OpcUa-Item")
    assert item["item"] == "/?id=ns=2;s=0:F17/PV/PV.CV"


def test_opcua_flow_inject_wires_to_item(built_flow):
    inject = next(n for n in built_flow if n["type"] == "inject")
    item = next(n for n in built_flow if n["type"] == "OpcUa-Item")
    assert item["id"] in inject["wires"][0]


def test_opcua_flow_item_wires_to_client(built_flow):
    item = next(n for n in built_flow if n["type"] == "OpcUa-Item")
    client = next(n for n in built_flow if n["type"] == "OpcUa-Client")
    assert client["id"] in item["wires"][0]


def test_opcua_flow_client_references_endpoint(built_flow):
    endpoint = next(n for n in built_flow if n["type"] == "OpcUa-Endpoint")
    client = next(n for n in built_flow if n["type"] == "OpcUa-Client")
    assert client["endpoint"] == endpoint["id"]
