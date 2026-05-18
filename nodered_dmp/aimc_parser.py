import base64

from nodered_dmp.aas_client import get_submodel_json


def resolve_relationship_to_reference(keys):
    if keys[0].get("type") == "Submodel":
        element_ref = "/submodels"
        submodel_id = keys.pop(0).get("value")
        base64_id = base64.b64encode(submodel_id.encode('utf-8')).decode('utf-8')
        element_ref = f"{element_ref}/{base64_id}/submodel-elements"
    else:
        raise Exception("First element of the relationship is not a Submodel")
    first_submodel_element = True
    for key in keys:
        delimiter = "."
        if first_submodel_element:
            delimiter = "/"
            first_submodel_element = False
        element_value = key.get("value")
        element_ref = f"{element_ref}{delimiter}{element_value}"
    return element_ref


def get_connections(aimc_url):
    aimc_json = get_submodel_json(aimc_url)
    connections = []
    for submodel_element in aimc_json.get("submodelElements"):
        for value in submodel_element.get("value"):
            connection = {"source_sink": []}
            for value_in_value in value.get("value"):
                semantic_ids = []

                if type(value_in_value.get("semanticId")) is dict:
                    for key in value_in_value.get("semanticId").get("keys"):
                        semantic_ids.append(key.get("value", ""))
                if "https://admin-shell.io/idta/AssetInterfacesMappingConfiguration/1/0/InterfaceReference" in semantic_ids:
                    interface_in_aas = resolve_relationship_to_reference(value_in_value.get("value").get("keys"))
                    connection["interface"] = interface_in_aas

                if type(value_in_value.get("semanticIdListElement")) is dict:
                    for key in value_in_value.get("semanticIdListElement").get("keys"):
                        semantic_ids.append(key.get("value", ""))
                if "https://admin-shell.io/idta/AssetInterfacesMappingConfiguration/1/0/MappingSourceSinkRelation" in semantic_ids:
                    for relationship in value_in_value.get("value"):
                        source_in_aas = resolve_relationship_to_reference(relationship.get("first").get("keys"))
                        sink_in_aas = resolve_relationship_to_reference(relationship.get("second").get("keys"))
                        connection["source_sink"].append((source_in_aas, sink_in_aas))
            connections.append(connection)
    return connections
