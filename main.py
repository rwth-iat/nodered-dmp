from nodered_dmp.aas.client import id_to_url
from nodered_dmp.aas.aas_to_etlpath import parse_aimc
from nodered_dmp.flow_builder import build_flow

# SUBMODEL_SERVER = "http://localhost:8081"
SUBMODEL_SERVER = "http://localhost:8080/api/v3.1"
AIMC_ID = "https://www.iat.rwth-aachen.de/pls-lab/pumping_station/TU10/F17/AssetInterfacesMappingConfiguration_v1"

if __name__ == "__main__":
    aimc_url = id_to_url(SUBMODEL_SERVER, AIMC_ID)
    etl_paths = parse_aimc(aimc_url, SUBMODEL_SERVER)
    flow = build_flow(etl_paths)
    print(flow.generate_json())
