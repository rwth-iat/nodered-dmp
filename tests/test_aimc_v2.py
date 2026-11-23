import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from nodered_dmp.aas import aas_to_etlpath as parser
from nodered_dmp.aas import writer
from nodered_dmp.aas.sync import sync_aas
from nodered_dmp.flow_builder import build_flow
from nodered_dmp.model import ETLPathStore

BASE = "http://localhost:8081"


@pytest.fixture
def mqtt_example(monkeypatch):
    example = Path(__file__).parents[1] / "examples/aimc-v2/MeasurementValue_Example.json"
    models = json.loads(example.read_text(encoding="utf8"))["submodels"]
    aimc, = (model for model in models if model["idShort"] == "AssetInterfacesMappingConfiguration")
    urls = {parser.id_to_url(BASE, model["id"]): model for model in models}
    def index_elements(elements, base, separator):
        for element in elements:
            path = base + separator + element["idShort"]
            urls[path] = element
            if element["modelType"] == "SubmodelElementCollection":
                index_elements(element.get("value", []), path, ".")

    aid = next(model for model in models if model["idShort"] == "AssetInterfacesDescription")
    index_elements(aid["submodelElements"], parser.id_to_url(BASE, aid["id"]), "/submodel-elements/")
    monkeypatch.setattr(parser, "get_submodel_json", lambda url, token: urls[url])
    monkeypatch.setattr(parser, "get_submodel_element_json", lambda url, token: urls[url])
    return parser.id_to_url(BASE, aimc["id"]), aimc, urls


def test_mqtt_example_sync_and_flow(mqtt_example, tmp_path):
    url, _, _ = mqtt_example
    store = ETLPathStore(str(tmp_path / "store.json"))
    paths = sync_aas(url, BASE, store).created
    assert {p.extract.href: p.load.idshort_path for p in paths} == {
        "/sampleDevice/properties/voltage": "MeasuredValue.Value",
        "/sampleDevice/properties/status": "MeasurementQualifier.Quality",
        "/sampleDevice/properties/timestamp": "MeasurementTimestamp",
    }
    assert {p.extract.protocol for p in paths} == {"mqtt"}
    result = sync_aas(url, BASE, store)
    assert not (result.created or result.updated or result.deleted)
    nodes = json.loads(build_flow(store.load_all()).generate_json())
    assert {n["topic"] for n in nodes if n["type"] == "mqtt in"} == {p.extract.href for p in paths}
    assert any(n.get("name") == "AASInterface" for n in nodes)


def test_ambiguous_live_sink(mqtt_example):
    url, aimc, _ = mqtt_example
    config = aimc["submodelElements"][0]["value"][0]
    sinks = parser._children(config)["Sinks"]["value"]
    sinks.append(sinks[0])
    with pytest.raises(ValueError, match=r"MappingConfigurations\[0\].*ambiguous"):
        parser.parse_aimc(url, BASE)


def test_missing_aid_metadata(mqtt_example):
    url, _, urls = mqtt_example
    for address, element in urls.items():
        if address.endswith(".voltage"):
            element["value"] = []
    with pytest.raises(ValueError, match="forms.href"):
        parser.parse_aimc(url, BASE)


def test_v2_writeback_is_rejected_before_api_calls(mqtt_example, monkeypatch):
    write_aid, write_aimc = Mock(), Mock()
    monkeypatch.setattr(writer, "write_aid_properties", write_aid)
    monkeypatch.setattr(writer, "write_aimc", write_aimc)
    with pytest.raises(ValueError, match="AIMC 2.0"):
        writer.write_to_aas(parser.parse_aimc(mqtt_example[0], BASE), BASE)
    write_aid.assert_not_called()
    write_aimc.assert_not_called()
