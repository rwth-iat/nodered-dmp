from itertools import groupby

from nodered_dmp.aas.client import put_submodel, put_submodel_element
from nodered_dmp.model.etl_path import ETLPath

_SEM_AIMC = "https://admin-shell.io/idta/AssetInterfacesMappingConfiguration/1/0/"

_SEM = {
    "submodel":      _SEM_AIMC + "Submodel",
    "configs":       _SEM_AIMC + "MappingConfigurations",
    "config":        _SEM_AIMC + "MappingConfiguration",
    "iface_ref":     _SEM_AIMC + "InterfaceReference",
    "relations":     _SEM_AIMC + "MappingSourceSinkRelations",
    "relation":      _SEM_AIMC + "MappingSourceSinkRelation",
}


def _ext_ref(value: str) -> dict:
    return {"keys": [{"type": "GlobalReference", "value": value}], "type": "ExternalReference"}


def _model_ref(*keys: tuple[str, str]) -> dict:
    return {
        "keys": [{"type": t, "value": v} for t, v in keys],
        "type": "ModelReference",
    }


def _sink_keys(submodel_id: str, idshort_path: str) -> list[tuple[str, str]]:
    segments = idshort_path.split(".")
    keys = [("Submodel", submodel_id)]
    for seg in segments[:-1]:
        keys.append(("SubmodelElementCollection", seg))
    keys.append(("Property", segments[-1]))
    return keys


def _source_keys(aid_submodel_id: str, aid_idshort_path: str) -> list[tuple[str, str]]:
    segments = aid_idshort_path.split(".")
    keys = [("Submodel", aid_submodel_id)]
    for seg in segments:
        keys.append(("SubmodelElementCollection", seg))
    return keys


def build_aimc_submodel(etl_paths: list[ETLPath]) -> dict:
    """
    Build a full AIMC submodel body from a list of ETLPaths.
    Paths without AASAnchor or AIDMetadata are skipped.
    The aimc_submodel_id is taken from the first path with a non-empty aas anchor.
    """
    aimc_id = next((p.aas.aimc_submodel_id for p in etl_paths if p.aas), "")

    paths_with_aas = [p for p in etl_paths if p.aas and p.aid and p.load.submodel_id]

    mapping_configs = []
    for interface_name, group in groupby(
        sorted(paths_with_aas, key=lambda p: p.aid.aid_idshort_path.split(".")[0]),
        key=lambda p: p.aid.aid_idshort_path.split(".")[0],
    ):
        group_paths = list(group)
        aid_submodel_id = group_paths[0].aid.aid_submodel_id

        relations = []
        for p in group_paths:
            relations.append({
                "modelType": "RelationshipElement",
                "first": _model_ref(*_source_keys(aid_submodel_id, p.aid.aid_idshort_path)),
                "second": _model_ref(*_sink_keys(p.load.submodel_id, p.load.idshort_path)),
            })

        mapping_configs.append({
            "modelType": "SubmodelElementCollection",
            "value": [
                {
                    "modelType": "ReferenceElement",
                    "idShort": "InterfaceReference",
                    "semanticId": _ext_ref(_SEM["iface_ref"]),
                    "value": _model_ref(("Submodel", aid_submodel_id), ("SubmodelElementCollection", interface_name)),
                },
                {
                    "modelType": "SubmodelElementList",
                    "idShort": "MappingSourceSinkRelations",
                    "orderRelevant": True,
                    "semanticId": _ext_ref(_SEM["relations"]),
                    "semanticIdListElement": _ext_ref(_SEM["relation"]),
                    "typeValueListElement": "RelationshipElement",
                    "value": relations,
                },
            ],
        })

    return {
        "modelType": "Submodel",
        "kind": "Instance",
        "id": aimc_id,
        "idShort": "AssetInterfacesMappingConfiguration",
        "semanticId": _ext_ref(_SEM["submodel"]),
        "submodelElements": [
            {
                "modelType": "SubmodelElementList",
                "idShort": "MappingConfigurations",
                "orderRelevant": True,
                "semanticId": _ext_ref(_SEM["configs"]),
                "semanticIdListElement": _ext_ref(_SEM["config"]),
                "typeValueListElement": "SubmodelElementCollection",
                "value": mapping_configs,
            }
        ],
    }


def write_aimc(etl_paths: list[ETLPath], server_base: str, access_token: str | None = None) -> None:
    """
    PUT each RelationshipElement to its indexed position in the AIMC submodel.
    Paths without AASAnchor or AIDMetadata are skipped.
    """
    for etl_path in etl_paths:
        if etl_path.aas is None or etl_path.aid is None or etl_path.load.submodel_id is None:
            continue
        body = {
            "modelType": "RelationshipElement",
            "first": _model_ref(*_source_keys(etl_path.aid.aid_submodel_id, etl_path.aid.aid_idshort_path)),
            "second": _model_ref(*_sink_keys(etl_path.load.submodel_id, etl_path.load.idshort_path)),
        }
        put_submodel_element(
            server_base,
            etl_path.aas.aimc_submodel_id,
            etl_path.aas.aimc_idshort_path,
            body,
            access_token,
        )
