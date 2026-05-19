from nodered_dmp.aas_client import id_to_url
from nodered_dmp.aimc_parser import get_connections
from nodered_dmp.flow_builder import build_flow

SUBMODEL_SERVER = "http://localhost:8081"
AIMC_ID = "https://www.iat.rwth-aachen.de/pls-lab/pumping_station/TU10/F17/AssetInterfacesMappingConfiguration_v1"

if __name__ == "__main__":
    connections = get_connections(id_to_url(SUBMODEL_SERVER, AIMC_ID))
    flow = build_flow(connections, SUBMODEL_SERVER)
    print(flow.generate_json())
