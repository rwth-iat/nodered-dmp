import json
from pathlib import Path
from unittest.mock import Mock, patch

from nodered_dmp.aas_client import (
    get_EndpointMetadata,
    get_InterfaceMetadata,
    get_host_and_port,
    id_to_url,
)

FIXTURES = Path(__file__).parent / "fixtures"
SERVER = "http://localhost:8081"


def fixture(name):
    m = Mock()
    m.json.return_value = json.loads((FIXTURES / name).read_text())
    return m


def test_id_to_url():
    import base64
    url = id_to_url("http://server:8081", "https://example.com/ids/sm/Test")
    b64 = base64.b64encode(b"https://example.com/ids/sm/Test").decode()
    assert url == f"http://server:8081/submodels/{b64}"


def test_get_host_and_port_mqtt():
    scheme, host, port = get_host_and_port("mqtt://localhost:1883")
    assert scheme == "mqtt"
    assert host == "localhost"
    assert port == 1883


def test_get_host_and_port_http():
    scheme, host, port = get_host_and_port("http://localhost:8083")
    assert scheme == "http"
    assert host == "localhost"
    assert port == 8083


def test_get_endpoint_metadata_mqtt():
    with patch("nodered_dmp.aas_client.requests.get", return_value=fixture("AssetInterfacesDescription__InterfaceMQTT.json")):
        result = get_EndpointMetadata(SERVER + "/some/path")
    assert result == "mqtt://localhost:1883"


def test_get_endpoint_metadata_http():
    with patch("nodered_dmp.aas_client.requests.get", return_value=fixture("AssetInterfacesDescription__InterfaceHTTP.json")):
        result = get_EndpointMetadata(SERVER + "/some/path")
    assert result == "http://localhost:8083"


def test_get_endpoint_metadata_modbus():
    with patch("nodered_dmp.aas_client.requests.get", return_value=fixture("AssetInterfacesDescription__InterfaceMODBUS.json")):
        result = get_EndpointMetadata(SERVER + "/some/path")
    assert result == "modbus+tcp://192.168.0.1:502/1"


def test_get_interface_metadata_voltage():
    with patch("nodered_dmp.aas_client.requests.get", return_value=fixture("AssetInterfacesDescription__InterfaceMQTT_InterfaceMetadata_Properties_voltage.json")):
        result = get_InterfaceMetadata(SERVER + "/some/path")
    assert result == "/sampleDevice/properties/voltage"


def test_get_interface_metadata_status():
    with patch("nodered_dmp.aas_client.requests.get", return_value=fixture("AssetInterfacesDescription__InterfaceMQTT_InterfaceMetadata_Properties_status.json")):
        result = get_InterfaceMetadata(SERVER + "/some/path")
    assert result == "/sampleDevice/properties/status"
