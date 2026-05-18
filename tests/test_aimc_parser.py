import base64
import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from nodered_dmp.aimc_parser import get_connections, resolve_relationship_to_reference

FIXTURES = Path(__file__).parent / "fixtures"
SERVER = "http://localhost:8081"


def fixture(name):
    m = Mock()
    m.json.return_value = json.loads((FIXTURES / name).read_text())
    return m


def test_resolve_relationship_to_reference():
    keys = [
        {"type": "Submodel", "value": "https://example.com/ids/sm/AssetInterfacesDescription"},
        {"type": "SubmodelElementCollection", "value": "InterfaceMQTT"},
        {"type": "Property", "value": "voltage"},
    ]
    b64 = base64.b64encode(b"https://example.com/ids/sm/AssetInterfacesDescription").decode()
    result = resolve_relationship_to_reference(keys)
    assert result == f"/submodels/{b64}/submodel-elements/InterfaceMQTT.voltage"


def test_resolve_relationship_to_reference_raises_if_not_submodel():
    keys = [{"type": "Property", "value": "something"}]
    with pytest.raises(Exception):
        resolve_relationship_to_reference(keys)


def test_get_connections_returns_three_interfaces():
    with patch("nodered_dmp.aas_client.requests.get", return_value=fixture("AssetInterfacesMappingConfiguration.json")):
        connections = get_connections(SERVER + "/submodels/abc")
    assert len(connections) == 3


def test_get_connections_interface_paths():
    with patch("nodered_dmp.aas_client.requests.get", return_value=fixture("AssetInterfacesMappingConfiguration.json")):
        connections = get_connections(SERVER + "/submodels/abc")
    interfaces = [c["interface"] for c in connections]
    assert any("InterfaceHTTP" in i for i in interfaces)
    assert any("InterfaceMODBUS" in i for i in interfaces)
    assert any("InterfaceMQTT" in i for i in interfaces)


def test_get_connections_source_sink_pairs():
    with patch("nodered_dmp.aas_client.requests.get", return_value=fixture("AssetInterfacesMappingConfiguration.json")):
        connections = get_connections(SERVER + "/submodels/abc")
    for conn in connections:
        assert "source_sink" in conn
        assert len(conn["source_sink"]) == 2
