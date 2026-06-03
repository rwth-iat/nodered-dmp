import tempfile

import pytest

from nodered_dmp.model import (
    AASAnchor,
    ETLPath,
    ETLPathStore,
    ExtractSpec,
    LoadSpec,
    NodeRedAnchor,
    TransformSpec,
)


def make_etl_path(**overrides) -> ETLPath:
    defaults = dict(
        aimc_submodel_id="https://example.com/aimc/1",
        aimc_idshort_path="MappingMQTT.Relations.voltage",
        extract=ExtractSpec(
            protocol="mqtt",
            endpoint="mqtt://localhost:1883",
            href="/device/voltage",
        ),
        transform=TransformSpec(),
        load=LoadSpec(
            sink_url="http://localhost:8081/submodels/abc/submodel-elements/voltage",
            submodel_id="https://example.com/sm/device",
            idshort_path="voltage",
        ),

    )
    defaults.update(overrides)
    return ETLPath(**defaults)


def test_etl_path_id_auto_generated():
    p = make_etl_path()
    assert p.etl_path_id
    assert len(p.etl_path_id) == 32  # uuid4().hex


def test_etl_path_ids_are_unique():
    assert make_etl_path().etl_path_id != make_etl_path().etl_path_id


def test_etl_path_roundtrip_json():
    p = make_etl_path()
    restored = ETLPath.model_validate_json(p.model_dump_json())
    assert restored == p


def test_etl_path_nodered_anchor_none_by_default():
    p = make_etl_path()
    assert p.nodered is None
    assert p.aas is None


def test_transform_default_function_code():
    p = make_etl_path()
    assert p.transform.function_code == "return msg;"


def test_transform_custom_function_code():
    p = make_etl_path(transform=TransformSpec(function_code="msg.payload = msg.payload * 2; return msg;"))
    assert "* 2" in p.transform.function_code


def test_etl_path_with_anchors():
    p = make_etl_path(
        nodered=NodeRedAnchor(
            endpoint_node_id="abc123",
            config_node_id="broker456",
            column_positions={"mqtt_in": 0, "change_1": 1},
        ),
        aas=AASAnchor(
            aid_submodel_id="https://example.com/aid/1",
            aid_idshort_path="InterfaceMQTT.InterfaceMetadata.Properties.voltage",
            title="voltage",
            unit="V",
            observable=True,
        ),
    )
    assert p.nodered.config_node_id == "broker456"
    assert p.aas.unit == "V"


def test_etl_path_roundtrip_with_anchors():
    p = make_etl_path(
        nodered=NodeRedAnchor(endpoint_node_id="abc123"),
        aas=AASAnchor(
            aid_submodel_id="https://example.com/aid/1",
            aid_idshort_path="InterfaceMQTT.InterfaceMetadata.Properties.voltage",
        ),
    )
    restored = ETLPath.model_validate_json(p.model_dump_json())
    assert restored.nodered.endpoint_node_id == "abc123"
    assert restored.aas.aid_submodel_id == "https://example.com/aid/1"


# --- Store tests ---

@pytest.fixture
def store(tmp_path):
    return ETLPathStore(path=str(tmp_path / "etl_paths.json"))


def test_store_save_and_load_all(store):
    p = make_etl_path()
    store.save(p)
    all_paths = store.load_all()
    assert len(all_paths) == 1
    assert all_paths[0] == p


def test_store_upsert_does_not_duplicate(store):
    p = make_etl_path()
    store.save(p)
    store.save(p)
    assert len(store.load_all()) == 1


def test_store_upsert_updates_existing(store):
    p = make_etl_path()
    store.save(p)
    p.nodered = NodeRedAnchor(endpoint_node_id="newnode")
    store.save(p)
    loaded = store.load_all()[0]
    assert loaded.nodered.endpoint_node_id == "newnode"


def test_store_find_by_node_id(store):
    p = make_etl_path(nodered=NodeRedAnchor(endpoint_node_id="target_node"))
    store.save(p)
    found = store.find_by_node_id("target_node")
    assert found is not None
    assert found.etl_path_id == p.etl_path_id


def test_store_find_by_node_id_returns_none_if_missing(store):
    store.save(make_etl_path())
    assert store.find_by_node_id("nonexistent") is None


def test_store_find_by_aimc_path(store):
    p = make_etl_path(
        aimc_submodel_id="https://example.com/aimc/1",
        aimc_idshort_path="MappingMQTT.Relations.voltage",
    )
    store.save(p)
    found = store.find_by_aimc_path(
        "https://example.com/aimc/1",
        "MappingMQTT.Relations.voltage",
    )
    assert found.etl_path_id == p.etl_path_id


def test_store_delete(store):
    p = make_etl_path()
    store.save(p)
    store.delete(p.etl_path_id)
    assert store.load_all() == []


def test_store_multiple_paths(store):
    paths = [make_etl_path() for _ in range(3)]
    for p in paths:
        store.save(p)
    assert len(store.load_all()) == 3
