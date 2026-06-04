import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from nodered_dmp.aas.aas_to_etlpath import parse_aimc

FIXTURES = Path(__file__).parent / "fixtures"
ARTIFACTS = Path(__file__).parent / "artifacts"
SERVER = "http://localhost:8081"
AIMC_URL = SERVER + "/submodels/abc"

# Mock call order mirrors the traversal order in parse_aimc:
#   1. AIMC submodel
#   2. InterfaceHTTP  (endpoint fetch → protocol "http" → skipped)
#   3. InterfaceMODBUS (endpoint fetch → protocol "modbus+tcp" → skipped)
#   4. InterfaceMQTT  (endpoint fetch → protocol "mqtt" → process)
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
def etl_paths():
    mocks = [_mock(f) for f in FIXTURE_SEQUENCE]
    with patch("nodered_dmp.aas.client.requests.get", side_effect=mocks):
        paths = parse_aimc(AIMC_URL, SERVER)
    ARTIFACTS.mkdir(exist_ok=True)
    (ARTIFACTS / "etl_paths_mqtt.json").write_text(
        json.dumps([json.loads(p.model_dump_json()) for p in paths], indent=2)
    )
    return paths


# --- count and protocol ---

def test_returns_only_mqtt_etl_paths(etl_paths):
    assert len(etl_paths) == 2


def test_all_paths_have_mqtt_protocol(etl_paths):
    assert all(p.extract.protocol == "mqtt" for p in etl_paths)


# --- AIMC identity (AASAnchor) ---

def test_aas_anchor_aimc_submodel_id(etl_paths):
    expected = "https://example.com/ids/sm/AssetInterfacesMappingConfiguration"
    assert all(p.aas.aimc_submodel_id == expected for p in etl_paths)


def test_aas_anchor_aimc_idshort_paths_are_unique(etl_paths):
    paths = [p.aas.aimc_idshort_path for p in etl_paths]
    assert len(set(paths)) == 2


def test_aas_anchor_aimc_idshort_path_format(etl_paths):
    # MQTT is at index 2 (HTTP=0, MODBUS=1, MQTT=2); relations at 0 and 1
    paths = {p.aas.aimc_idshort_path for p in etl_paths}
    assert "MappingConfigurations[2].MappingSourceSinkRelations[0]" in paths
    assert "MappingConfigurations[2].MappingSourceSinkRelations[1]" in paths


# --- ExtractSpec ---

def test_extract_endpoint(etl_paths):
    assert all(p.extract.endpoint == "mqtt://localhost:1883" for p in etl_paths)


def test_extract_hrefs(etl_paths):
    hrefs = {p.extract.href for p in etl_paths}
    assert "/sampleDevice/properties/voltage" in hrefs
    assert "/sampleDevice/properties/status" in hrefs


def test_extract_control_packet_voltage(etl_paths):
    voltage = next(p for p in etl_paths if "voltage" in p.extract.href)
    assert voltage.extract.control_packet == "subscribe"


def test_extract_control_packet_status(etl_paths):
    status = next(p for p in etl_paths if "status" in p.extract.href)
    assert status.extract.control_packet == "publish"


# --- TransformSpec ---

def test_transform_defaults_to_passthrough(etl_paths):
    assert all(p.transform.function_code == "return msg;" for p in etl_paths)


# --- LoadSpec ---

def test_load_sink_url_contains_server(etl_paths):
    assert all(p.load.sink_url.startswith(SERVER) for p in etl_paths)


def test_load_sink_url_voltage(etl_paths):
    voltage = next(p for p in etl_paths if "voltage" in p.extract.href)
    assert "MQTT_Data" in voltage.load.sink_url
    assert "voltage" in voltage.load.sink_url


def test_load_sink_submodel_id(etl_paths):
    assert all(
        p.load.submodel_id == "https://example.com/ids/sm/OperationalData"
        for p in etl_paths
    )


def test_load_sink_idshort_path_voltage(etl_paths):
    voltage = next(p for p in etl_paths if "voltage" in p.extract.href)
    assert voltage.load.idshort_path == "MQTT_Data.voltage"


# --- AASAnchor populated ---

def test_aas_anchor_populated(etl_paths):
    assert all(p.aas is not None for p in etl_paths)


# --- AIDMetadata ---

def test_aid_metadata_populated(etl_paths):
    assert all(p.aid is not None for p in etl_paths)


def test_aid_metadata_aid_submodel_id(etl_paths):
    expected = "https://example.com/ids/sm/AssetInterfacesDescription"
    assert all(p.aid.aid_submodel_id == expected for p in etl_paths)


def test_aid_metadata_voltage_title(etl_paths):
    voltage = next(p for p in etl_paths if "voltage" in p.extract.href)
    assert voltage.aid.title == "voltage"


def test_aid_metadata_voltage_unit(etl_paths):
    voltage = next(p for p in etl_paths if "voltage" in p.extract.href)
    assert voltage.aid.unit == "V"


def test_aid_metadata_voltage_data_type(etl_paths):
    voltage = next(p for p in etl_paths if "voltage" in p.extract.href)
    assert voltage.aid.data_type == "integer"


def test_aid_metadata_voltage_observable(etl_paths):
    voltage = next(p for p in etl_paths if "voltage" in p.extract.href)
    assert voltage.aid.observable is True


def test_aid_metadata_voltage_value_range(etl_paths):
    voltage = next(p for p in etl_paths if "voltage" in p.extract.href)
    assert voltage.aid.value_range == ("1", "100")


def test_aid_metadata_status_not_observable(etl_paths):
    status = next(p for p in etl_paths if "status" in p.extract.href)
    assert status.aid.observable is False


def test_aid_metadata_status_unit_is_none(etl_paths):
    status = next(p for p in etl_paths if "status" in p.extract.href)
    assert status.aid.unit is None


# --- NodeRedAnchor ---

def test_nodered_anchor_not_populated(etl_paths):
    assert all(p.nodered is None for p in etl_paths)


# ============================================================
# OPC UA fixture sequence (pumping station TU10/F17)
# ============================================================
#
# parse_aimc fetches:
#   1. AIMC submodel (1 MappingConfig → InterfaceOPCUA, 1 relation)
#   2. InterfaceOPCUA (endpoint: opc.tcp://localhost:9409/..., scheme → "opcua")
#   3. CurrentValue property (href: /?id=ns=2;s=0:F17/PV/PV.CV)

OPCUA_FIXTURE_SEQUENCE = [
    "AssetInterfacesMappingConfiguration__TU10_F17.json",
    "AssetInterfacesDescription__TU10_F17__InterfaceOPCUA.json",
    "AssetInterfacesDescription__TU10_F17__InterfaceOPCUA_properties_CurrentValue.json",
]

OPCUA_AIMC_URL = SERVER + "/submodels/opcua-aimc"


@pytest.fixture
def opcua_etl_paths():
    mocks = [_mock(f) for f in OPCUA_FIXTURE_SEQUENCE]
    with patch("nodered_dmp.aas.client.requests.get", side_effect=mocks):
        return parse_aimc(OPCUA_AIMC_URL, SERVER)


def test_opcua_returns_one_path(opcua_etl_paths):
    assert len(opcua_etl_paths) == 1


def test_opcua_protocol(opcua_etl_paths):
    assert opcua_etl_paths[0].extract.protocol == "opcua"


def test_opcua_endpoint(opcua_etl_paths):
    assert opcua_etl_paths[0].extract.endpoint == "opc.tcp://localhost:9409/DvOpcUaServer"


def test_opcua_href_strips_id_prefix(opcua_etl_paths):
    # AID href is "/?id=ns=2;s=0:F17/PV/PV.CV" — prefix must be stripped
    assert opcua_etl_paths[0].extract.href == "ns=2;s=0:F17/PV/PV.CV"


def test_opcua_aas_anchor_populated(opcua_etl_paths):
    p = opcua_etl_paths[0]
    assert p.aas is not None
    assert p.aas.aimc_idshort_path == "MappingConfigurations[0].MappingSourceSinkRelations[0]"


def test_opcua_aid_metadata_populated(opcua_etl_paths):
    p = opcua_etl_paths[0]
    assert p.aid is not None
    assert p.aid.title == "Current Value"
    assert p.aid.data_type == "float"
    assert p.aid.observable is True
