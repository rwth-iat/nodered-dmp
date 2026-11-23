# AIMC examples

Run these demos from the **nodered-dmp repository root** in Windows PowerShell.
Install Docker Desktop with Docker Compose, Python 3.14+ and uv, and start Docker Desktop.
The DMP dependency `nodered-flowgen` must be checked out next to this repository.

```text
workspace/
  nodered-dmp/       # Run every command from here
  nodered-flowgen/
```

```powershell
uv sync
docker compose version
```

## Start the services

```powershell
$ErrorActionPreference = 'Stop'
$compose = @('-f', 'examples/compose.yaml')
docker compose @compose up -d
if ($LASTEXITCODE) { throw 'Compose did not start the demo.' }
& ./examples/wait-for-services.ps1
$deadline = (Get-Date).AddSeconds(60)
do {
    docker compose @compose exec -T mqtt mosquitto_pub -h 127.0.0.1 -t /dmp/readiness -m ready
    if ($LASTEXITCODE -eq 0) { break }
    if ((Get-Date) -ge $deadline) { throw 'The data source did not become ready.' }
    Start-Sleep -Seconds 2
} while ($true)
```

Pick one demo and continue in the same PowerShell session:

- [AIMC 1.0 · MQTT to OperationalData](aimc-v1/README.md)
- [AIMC 2.0 · MQTT to MeasurementValue](aimc-v2/README.md)

Both demos use BaSyx on port 8081 and the Node-RED editor on port 1880.
Run one demo at a time. Both AASX packages have the same shell ID.
Before switching versions, stop the stack with the following command.
Then run the start commands above and import the other package.

```powershell
docker compose -f examples/compose.yaml down
```

BaSyx stores data in memory. Import the AASX again after creating a new
container. The local DMP stores and generated flow files remain under `tmp/`.
