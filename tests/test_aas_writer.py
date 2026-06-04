import json
from pathlib import Path
from unittest.mock import Mock, call, patch

import pytest

from nodered_dmp.aas.aid_builder import build_property_element, write_aid_properties
from nodered_dmp.aas.aimc_builder import build_aimc_submodel, write_aimc
from nodered_dmp.aas.aas_to_etlpath import parse_aimc
from nodered_dmp.aas.writer import write_to_aas

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
def etl_paths():
    mocks = [_mock(f) for f in FIXTURE_SEQUENCE]
    with patch("nodered_dmp.aas.client.requests.get", side_effect=mocks):
        return parse_aimc(AIMC_URL, SERVER)


# === build_property_element ===

def test_property_element_model_type(etl_paths):
    voltage = next(p for p in etl_paths if "voltage" in p.extract.href)
    elem = build_property_element(voltage)
    assert elem["modelType"] == "SubmodelElementCollection"


def test_property_element_idshort(etl_paths):
    voltage = next(p for p in etl_paths if "voltage" in p.extract.href)
    elem = build_property_element(voltage)
    assert elem["idShort"] == "voltage"


def test_property_element_href(etl_paths):
    voltage = next(p for p in etl_paths if "voltage" in p.extract.href)
    elem = build_property_element(voltage)
    forms = next(e for e in elem["value"] if e["idShort"] == "forms")
    href = next(e for e in forms["value"] if e["idShort"] == "href")
    assert href["value"] == "/sampleDevice/properties/voltage"


def test_property_element_control_packet(etl_paths):
    voltage = next(p for p in etl_paths if "voltage" in p.extract.href)
    elem = build_property_element(voltage)
    forms = next(e for e in elem["value"] if e["idShort"] == "forms")
    cp = next(e for e in forms["value"] if e["idShort"] == "mqv_controlPacket")
    assert cp["value"] == "subscribe"


def test_property_element_unit(etl_paths):
    voltage = next(p for p in etl_paths if "voltage" in p.extract.href)
    elem = build_property_element(voltage)
    unit = next(e for e in elem["value"] if e["idShort"] == "unit")
    assert unit["value"] == "V"


def test_property_element_value_range(etl_paths):
    voltage = next(p for p in etl_paths if "voltage" in p.extract.href)
    elem = build_property_element(voltage)
    r = next(e for e in elem["value"] if e.get("modelType") == "Range")
    assert r["min"] == "1"
    assert r["max"] == "100"


def test_property_element_observable_true(etl_paths):
    voltage = next(p for p in etl_paths if "voltage" in p.extract.href)
    elem = build_property_element(voltage)
    obs = next(e for e in elem["value"] if e["idShort"] == "observable")
    assert obs["value"] == "true"


def test_property_element_observable_false(etl_paths):
    status = next(p for p in etl_paths if "status" in p.extract.href)
    elem = build_property_element(status)
    obs = next(e for e in elem["value"] if e["idShort"] == "observable")
    assert obs["value"] == "false"


def test_property_element_no_unit_for_status(etl_paths):
    status = next(p for p in etl_paths if "status" in p.extract.href)
    elem = build_property_element(status)
    unit = next((e for e in elem["value"] if e["idShort"] == "unit"), None)
    assert unit is None or unit.get("value") in (None, "")


def test_property_element_raises_without_aid_metadata(etl_paths):
    voltage = next(p for p in etl_paths if "voltage" in p.extract.href)
    voltage.aid = None
    with pytest.raises(ValueError):
        build_property_element(voltage)


# === build_aimc_submodel ===

def test_aimc_submodel_model_type(etl_paths):
    body = build_aimc_submodel(etl_paths)
    assert body["modelType"] == "Submodel"


def test_aimc_submodel_id(etl_paths):
    body = build_aimc_submodel(etl_paths)
    assert body["id"] == "https://example.com/ids/sm/AssetInterfacesMappingConfiguration"


def test_aimc_submodel_has_mapping_configurations(etl_paths):
    body = build_aimc_submodel(etl_paths)
    configs = body["submodelElements"][0]
    assert configs["idShort"] == "MappingConfigurations"
    assert len(configs["value"]) == 1  # one interface group: InterfaceMQTT


def test_aimc_submodel_interface_reference(etl_paths):
    body = build_aimc_submodel(etl_paths)
    config = body["submodelElements"][0]["value"][0]
    iface_ref = next(e for e in config["value"] if e["idShort"] == "InterfaceReference")
    keys = iface_ref["value"]["keys"]
    assert keys[0]["value"] == "https://example.com/ids/sm/AssetInterfacesDescription"
    assert keys[1]["value"] == "InterfaceMQTT"


def test_aimc_submodel_has_two_relations(etl_paths):
    body = build_aimc_submodel(etl_paths)
    config = body["submodelElements"][0]["value"][0]
    relations = next(e for e in config["value"] if e["idShort"] == "MappingSourceSinkRelations")
    assert len(relations["value"]) == 2


def test_aimc_submodel_voltage_source_keys(etl_paths):
    body = build_aimc_submodel(etl_paths)
    config = body["submodelElements"][0]["value"][0]
    relations = next(e for e in config["value"] if e["idShort"] == "MappingSourceSinkRelations")
    voltage_rel = next(
        r for r in relations["value"]
        if r["first"]["keys"][-1]["value"] == "voltage"
    )
    source_keys = voltage_rel["first"]["keys"]
    assert source_keys[0]["value"] == "https://example.com/ids/sm/AssetInterfacesDescription"
    assert source_keys[-1]["value"] == "voltage"


def test_aimc_submodel_voltage_sink_keys(etl_paths):
    body = build_aimc_submodel(etl_paths)
    config = body["submodelElements"][0]["value"][0]
    relations = next(e for e in config["value"] if e["idShort"] == "MappingSourceSinkRelations")
    voltage_rel = next(
        r for r in relations["value"]
        if r["first"]["keys"][-1]["value"] == "voltage"
    )
    sink_keys = voltage_rel["second"]["keys"]
    assert sink_keys[0]["value"] == "https://example.com/ids/sm/OperationalData"
    assert sink_keys[-1]["value"] == "voltage"
    assert sink_keys[-1]["type"] == "Property"


# === HTTP calls ===

def test_write_aid_properties_puts_each_path(etl_paths):
    with patch("nodered_dmp.aas.client.requests.put") as mock_put:
        write_aid_properties(etl_paths, SERVER)
    assert mock_put.call_count == 2


def test_write_aid_properties_url_contains_idshort_path(etl_paths):
    with patch("nodered_dmp.aas.client.requests.put") as mock_put:
        write_aid_properties(etl_paths, SERVER)
    urls = [c.args[0] for c in mock_put.call_args_list]
    assert any("voltage" in u for u in urls)
    assert any("status" in u for u in urls)


def test_write_aimc_puts_once_per_path(etl_paths):
    with patch("nodered_dmp.aas.client.requests.put") as mock_put:
        write_aimc(etl_paths, SERVER)
    assert mock_put.call_count == 2  # one PUT per ETLPath with AASAnchor


def test_write_aimc_url_contains_indexed_path(etl_paths):
    with patch("nodered_dmp.aas.client.requests.put") as mock_put:
        write_aimc(etl_paths, SERVER)
    urls = [c.args[0] for c in mock_put.call_args_list]
    assert any("MappingConfigurations%5B2%5D" in u or "MappingConfigurations[2]" in u or "MappingSourceSinkRelations" in u for u in urls)


def test_write_to_aas_puts_four_times(etl_paths):
    with patch("nodered_dmp.aas.client.requests.put") as mock_put:
        write_to_aas(etl_paths, SERVER)
    assert mock_put.call_count == 4  # 2 AID property elements + 2 AIMC relations


def test_write_to_aas_skips_paths_without_aas_anchor(etl_paths):
    for p in etl_paths:
        p.aas = None
        p.aid = None
    with patch("nodered_dmp.aas.client.requests.put") as mock_put:
        write_to_aas(etl_paths, SERVER)
    assert mock_put.call_count == 0
