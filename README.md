# nodered-dmp — Node-RED Data Mapping Processor

Automatically generates Node-RED flows from an [Asset Administration Shell (AAS)](https://industrialdigitaltwin.org/en/content-hub/aasspecifications) server. It reads the Asset Interfaces Mapping Configuration (AIMC) submodel and produces a ready-to-import Node-RED flow that routes data between device interfaces (MQTT, OPC UA).

## How it works

1. Connects to an AAS server and fetches the AIMC submodel
2. Parses the source→sink mapping between device interfaces
3. Generates a Node-RED flow with the appropriate nodes and wiring

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- A running AAS server with an AIMC submodel

## Setup

```bash
git clone <repo>
cd nodered-dmp
uv sync
```

This project also depends on [nodered-flowgen](https://github.com/rwth-iat/nodered-flowgen) as a local editable package. Clone it alongside this repo:

```bash
git clone https://github.com/rwth-iat/nodered-flowgen ../nodered-flowgen
```

## Examples

[Set up and run either AIMC demo](examples/README.md).

## Testing

```bash
uv run pytest
```

After each test run, the generated flow is saved to `tests/artifacts/flow.json` for manual inspection.

## Supported mappings

AIMC 1.0 and 2.0 support direct MQTT and OPC UA mappings to Property elements in any target submodel. MeasurementValue is an example, not a requirement. HTTP, Modbus and BACnet adapters are not implemented.

AIMC 2.0 matches SourceId and SinkId. Lua transformations and AIMC 2.0 configuration write-back are not supported. OPC UA uses the existing one-second polling reader; automatic splitting of value, quality and timestamp is not supported.

## Project structure

- `nodered_dmp/aas/`: AID/AIMC import and configuration writing.
- `nodered_dmp/protocols/`: registered MQTT and OPC UA adapters.
- `nodered_dmp/flow_builder/`: shared Node-RED flow generation.
- `nodered_dmp/parse/`: flow import and synchronization.
- `examples/`: AIMC examples and MQTT demo stack. OPC UA requires its Node-RED palette separately.
- `tests/`: automated tests.
