from uuid import uuid4

from pydantic import BaseModel, Field


class ExtractSpec(BaseModel):
    protocol: str               # mqtt | http | opc.tcp | modbus+tcp | bacnet
    endpoint: str               # base URL / broker address (e.g. mqtt://localhost:1883)
    href: str                   # MQTT topic / HTTP path / OPC UA NodeId
    control_packet: str | None = None   # MQTT: subscribe | publish


class TransformSpec(BaseModel):
    function_code: str = "return msg;"  # JS source in the Function node — user-configurable only


class LoadSpec(BaseModel):
    sink_url: str                       # full HTTP URL used by Node-RED Change node (PUT endpoint)
    submodel_id: str | None = None      # AAS submodel ID of the sink property (None when parsed from flow only)
    idshort_path: str | None = None     # idShort path within that submodel (None when parsed from flow only)


class NodeRedAnchor(BaseModel):
    endpoint_node_id: str               # MQTTIn / OpcUaItem / HTTPRequest node hex ID
    config_node_id: str | None = None   # MQTTBroker / OpcUaEndpoint node hex ID
    column_positions: dict[str, int] = {}


class AASAnchor(BaseModel):
    aid_submodel_id: str        # AID submodel ID (URI)
    aid_idshort_path: str       # idShort path to the property within AID
    title: str | None = None
    data_type: str | None = None
    unit: str | None = None
    observable: bool = False
    value_range: tuple[str, str] | None = None


class ETLPath(BaseModel):
    etl_path_id: str = Field(default_factory=lambda: uuid4().hex)
    aimc_submodel_id: str       # AIMC submodel ID → used as Node-RED flow tab label
    aimc_idshort_path: str      # idShort path to the source/sink relation in AIMC

    extract: ExtractSpec
    transform: TransformSpec
    load: LoadSpec

    nodered: NodeRedAnchor | None = None    # populated by flow_builder
    aas: AASAnchor | None = None            # populated by aas_to_etlpath
