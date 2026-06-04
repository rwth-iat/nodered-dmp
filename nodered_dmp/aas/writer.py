from nodered_dmp.aas.aid_builder import write_aid_properties
from nodered_dmp.aas.aimc_builder import write_aimc
from nodered_dmp.model.etl_path import ETLPath


def write_to_aas(etl_paths: list[ETLPath], server_base: str) -> None:
    """
    Write ETLPaths back to the AAS server.

    Calls PUT on each AID property element (surgical update, preserves other interfaces)
    and PUT on the full AIMC submodel.

    ETLPaths without an AASAnchor are silently skipped — the AID submodel ID is required
    to locate the element on the server. Populate aas anchors via parse_aimc or sync_aas
    before calling this function.
    """
    write_aid_properties(etl_paths, server_base)
    write_aimc(etl_paths, server_base)
