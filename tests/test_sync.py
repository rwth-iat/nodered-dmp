import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from nodered_dmp.aas.aas_to_etlpath import parse_aimc
from nodered_dmp.aas.sync import sync_aas
from nodered_dmp.flow_builder import build_and_store_flow, build_flow
from nodered_dmp.model.store import ETLPathStore
from nodered_dmp.parse.sync import sync_flow

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
def store(tmp_path):
    return ETLPathStore(str(tmp_path / "etl_paths.json"))


@pytest.fixture
def flow_nodes():
    mocks = [_mock(f) for f in FIXTURE_SEQUENCE]
    with patch("nodered_dmp.aas.client.requests.get", side_effect=mocks):
        etl_paths = parse_aimc(AIMC_URL, SERVER)
    flow = build_flow(etl_paths)
    return json.loads(flow.generate_json())


# === sync_flow ===

def test_sync_flow_creates_new_paths(store, flow_nodes):
    result = sync_flow(flow_nodes, store)
    assert len(result.created) == 2
    assert result.updated == []
    assert result.deleted == []


def test_sync_flow_saves_to_store(store, flow_nodes):
    sync_flow(flow_nodes, store)
    assert len(store.load_all()) == 2


def test_sync_flow_second_run_updates_not_creates(store, flow_nodes):
    sync_flow(flow_nodes, store)
    result = sync_flow(flow_nodes, store)
    assert result.created == []
    assert len(result.updated) == 2
    assert result.deleted == []


def test_sync_flow_update_preserves_uuid(store, flow_nodes):
    first = sync_flow(flow_nodes, store)
    first_ids = {p.etl_path_id for p in first.created}
    second = sync_flow(flow_nodes, store)
    second_ids = {after.etl_path_id for _, after in second.updated}
    assert first_ids == second_ids


def test_sync_flow_recovers_modified_function_code(store, flow_nodes):
    sync_flow(flow_nodes, store)

    custom_code = "msg.payload = msg.payload * 2; return msg;"
    modified = json.loads(json.dumps(flow_nodes))
    for node in modified:
        if node["type"] == "function":
            node["func"] = custom_code

    result = sync_flow(modified, store)
    assert len(result.updated) == 2
    assert all(after.transform.function_code == custom_code for _, after in result.updated)


def test_sync_flow_updated_before_reflects_old_value(store, flow_nodes):
    sync_flow(flow_nodes, store)

    modified = json.loads(json.dumps(flow_nodes))
    new_code = "msg.payload = 42; return msg;"
    for node in modified:
        if node["type"] == "function":
            node["func"] = new_code

    result = sync_flow(modified, store)
    for before, _ in result.updated:
        assert before.transform.function_code == "return msg;"


def test_sync_flow_detects_deleted_path(store, flow_nodes):
    sync_flow(flow_nodes, store)

    # Remove one mqtt in node and its chain from the flow
    mqtt_in = next(n for n in flow_nodes if n["type"] == "mqtt in")
    trimmed = [n for n in flow_nodes if n["id"] != mqtt_in["id"]]

    result = sync_flow(trimmed, store)
    assert len(result.deleted) == 1
    assert len(store.load_all()) == 1


def test_sync_flow_preserves_aas_anchor(store):
    mocks = [_mock(f) for f in FIXTURE_SEQUENCE]
    with patch("nodered_dmp.aas.client.requests.get", side_effect=mocks):
        aas_paths = parse_aimc(AIMC_URL, SERVER)
    flow = build_and_store_flow(aas_paths, store)

    nodes = json.loads(flow.generate_json())
    sync_flow(nodes, store)

    for stored in store.load_all():
        assert stored.aas is not None


# === sync_aas ===

def test_sync_aas_creates_new_paths(store):
    mocks = [_mock(f) for f in FIXTURE_SEQUENCE]
    with patch("nodered_dmp.aas.client.requests.get", side_effect=mocks):
        result = sync_aas(AIMC_URL, SERVER, store)
    assert len(result.created) == 2
    assert result.updated == []
    assert result.deleted == []


def test_sync_aas_saves_to_store(store):
    mocks = [_mock(f) for f in FIXTURE_SEQUENCE]
    with patch("nodered_dmp.aas.client.requests.get", side_effect=mocks):
        sync_aas(AIMC_URL, SERVER, store)
    assert len(store.load_all()) == 2


def test_sync_aas_second_run_updates_not_creates(store):
    for _ in range(2):
        mocks = [_mock(f) for f in FIXTURE_SEQUENCE]
        with patch("nodered_dmp.aas.client.requests.get", side_effect=mocks):
            result = sync_aas(AIMC_URL, SERVER, store)
    assert result.created == []
    assert len(result.updated) == 2


def test_sync_aas_update_preserves_uuid(store):
    mocks = [_mock(f) for f in FIXTURE_SEQUENCE]
    with patch("nodered_dmp.aas.client.requests.get", side_effect=mocks):
        first = sync_aas(AIMC_URL, SERVER, store)
    first_ids = {p.etl_path_id for p in first.created}

    mocks = [_mock(f) for f in FIXTURE_SEQUENCE]
    with patch("nodered_dmp.aas.client.requests.get", side_effect=mocks):
        second = sync_aas(AIMC_URL, SERVER, store)
    second_ids = {after.etl_path_id for _, after in second.updated}
    assert first_ids == second_ids


def test_sync_aas_preserves_nodered_anchor(store):
    mocks = [_mock(f) for f in FIXTURE_SEQUENCE]
    with patch("nodered_dmp.aas.client.requests.get", side_effect=mocks):
        aas_paths = parse_aimc(AIMC_URL, SERVER)
    build_and_store_flow(aas_paths, store)

    # Re-sync from AAS — should update volatile fields but preserve nodered
    mocks = [_mock(f) for f in FIXTURE_SEQUENCE]
    with patch("nodered_dmp.aas.client.requests.get", side_effect=mocks):
        sync_aas(AIMC_URL, SERVER, store)

    for stored in store.load_all():
        assert stored.nodered is not None
