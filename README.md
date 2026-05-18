# nodered-dmp — Node-RED Data Mapping Processor

Automatically generates Node-RED flows from an [Asset Administration Shell (AAS)](https://industrialdigitaltwin.org/en/content-hub/aasspecifications) server. It reads the Asset Interfaces Mapping Configuration (AIMC) submodel and produces a ready-to-import Node-RED flow that routes data between device interfaces (MQTT, HTTP, MODBUS).

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

## Configuration

Edit `main.py` to point to your AAS server:

```python
SUBMODEL_SERVER = "http://localhost:8081"
AIMC_ID = "https://example.com/ids/sm/AssetInterfacesMappingConfiguration"
```

## Running

```bash
uv run main.py
```

The generated flow is printed to stdout as JSON. Import it directly into Node-RED via **Menu → Import**.

## Testing

```bash
uv run pytest
```

After each test run, the generated flow is saved to `tests/artifacts/flow.json` for manual inspection.

## Project structure

```
nodered_dmp/
├── aas_client.py     # HTTP communication with AAS server
├── aimc_parser.py    # parses AIMC submodel → structured connections
└── flow_builder.py   # builds Node-RED flow from parsed connections
main.py               # entry point
examples/             # example AAS packages (.aasx)
tests/
├── fixtures/         # real AAS server responses used as mock data
└── artifacts/        # generated flow output (gitignored)
```
