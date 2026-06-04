import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from nodered_dmp.aas.aas_to_etlpath import parse_aimc
from nodered_dmp.flow_builder import build_flow
from nodered_dmp.parse import parse_flow

FIXTURES = Path(__file__).parent / "fixtures"
SERVER = "http://localhost:8081"
AIMC_URL = SERVER + "/submodels/abc"

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
def built_etl_paths():
    mocks = [_mock(f) for f in FIXTURE_SEQUENCE]
    with patch("nodered_dmp.aas.client.requests.get", side_effect=mocks):
        return parse_aimc(AIMC_URL, SERVER)


@pytest.fixture
def flow_nodes(built_etl_paths):
    flow = build_flow(built_etl_paths)
    return json.loads(flow.generate_json())


@pytest.fixture
def parsed_paths(flow_nodes):
    return parse_flow(flow_nodes)


# --- count and protocol ---

def test_parse_flow_returns_two_paths(parsed_paths):
    assert len(parsed_paths) == 2


def test_parse_flow_protocol_is_mqtt(parsed_paths):
    assert all(p.extract.protocol == "mqtt" for p in parsed_paths)


# --- extract fields ---

def test_parse_flow_endpoint(parsed_paths):
    assert all(p.extract.endpoint == "mqtt://localhost:1883" for p in parsed_paths)


def test_parse_flow_hrefs(parsed_paths):
    hrefs = {p.extract.href for p in parsed_paths}
    assert "/sampleDevice/properties/voltage" in hrefs
    assert "/sampleDevice/properties/status" in hrefs


# --- transform fields ---

def test_parse_flow_default_function_code(parsed_paths):
    assert all(p.transform.function_code == "return msg;" for p in parsed_paths)


# --- load fields ---

def test_parse_flow_sink_url_contains_server(parsed_paths):
    assert all(p.load.sink_url.startswith(SERVER) for p in parsed_paths)


def test_parse_flow_sink_url_voltage(parsed_paths):
    voltage = next(p for p in parsed_paths if "voltage" in p.extract.href)
    assert "MQTT_Data" in voltage.load.sink_url
    assert "voltage" in voltage.load.sink_url


# --- nodered anchor ---

def test_parse_flow_nodered_anchor_populated(parsed_paths):
    assert all(p.nodered is not None for p in parsed_paths)


def test_parse_flow_endpoint_node_id_is_mqtt_in(parsed_paths, flow_nodes):
    mqtt_in_ids = {n["id"] for n in flow_nodes if n["type"] == "mqtt in"}
    parsed_ids = {p.nodered.endpoint_node_id for p in parsed_paths}
    assert parsed_ids == mqtt_in_ids


def test_parse_flow_config_node_id_is_broker(parsed_paths, flow_nodes):
    broker_id = next(n["id"] for n in flow_nodes if n["type"] == "mqtt-broker")
    assert all(p.nodered.config_node_id == broker_id for p in parsed_paths)


# --- aas anchor absent ---

def test_parse_flow_aas_anchor_is_none(parsed_paths):
    assert all(p.aas is None for p in parsed_paths)


def test_parse_flow_aid_metadata_is_none(parsed_paths):
    assert all(p.aid is None for p in parsed_paths)


# --- round-trip: modified function code is recovered ---

def test_parse_flow_recovers_modified_function_code(flow_nodes):
    custom_code = "msg.payload = msg.payload * 2; return msg;"
    modified = json.loads(json.dumps(flow_nodes))
    for node in modified:
        if node["type"] == "function":
            node["func"] = custom_code

    parsed = parse_flow(modified)
    assert all(p.transform.function_code == custom_code for p in parsed)


# --- round-trip: full field recovery matches original ETLPaths ---

def test_parse_flow_round_trip_hrefs_match(built_etl_paths, parsed_paths):
    original_hrefs = {p.extract.href for p in built_etl_paths}
    parsed_hrefs = {p.extract.href for p in parsed_paths}
    assert original_hrefs == parsed_hrefs


def test_parse_flow_round_trip_sink_urls_match(built_etl_paths, parsed_paths):
    original_urls = {p.load.sink_url for p in built_etl_paths}
    parsed_urls = {p.load.sink_url for p in parsed_paths}
    assert original_urls == parsed_urls
