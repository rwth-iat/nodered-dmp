# AIMC 2.0 · MQTT to MeasurementValue

Complete the [common setup](../README.md), then run the following from the repository root.

## Import and deploy

Import once per fresh BaSyx container. Reuse the same repository-root PowerShell session.

```powershell
$server = 'http://127.0.0.1:8081'
New-Item -ItemType Directory -Force tmp | Out-Null
curl.exe -f -sS -H 'Accept: application/json' -F 'file=@examples/aimc-v2/MeasurementValue_Example.aasx;type=application/asset-administration-shell-package' "$server/upload"
if ($LASTEXITCODE) { throw 'AASX upload failed.' }
$aimc = uv run python -c "from nodered_dmp.aas.client import id_to_url; print(id_to_url('$server', 'https://example.com/ids/sm/AssetInterfacesMappingConfiguration/2/0'))"
uv run python main.py --store tmp/aimc-v2-mqtt-store.json sync-aas --server $server --aimc-url $aimc
if ($LASTEXITCODE) { throw 'DMP command failed.' }
uv run python main.py --store tmp/aimc-v2-mqtt-store.json build-flow --label 'AIMC 2.0 - MeasurementValue' --output tmp/aimc-v2-mqtt-flow.json --nodered-server http://127.0.0.1:1880
if ($LASTEXITCODE) { throw 'DMP command failed.' }
```

## Verify live data

```powershell
$timestamp = '2026-11-23T12:00:00Z'
docker compose @compose exec -T mqtt mosquitto_pub -h 127.0.0.1 -q 2 -t /sampleDevice/properties/voltage -m 230
docker compose @compose exec -T mqtt mosquitto_pub -h 127.0.0.1 -q 2 -t /sampleDevice/properties/status -m good
docker compose @compose exec -T mqtt mosquitto_pub -h 127.0.0.1 -q 2 -t /sampleDevice/properties/timestamp -m $timestamp
$target = uv run python -c "from nodered_dmp.aas.client import id_to_url; print(id_to_url('$server', 'https://example.com/ids/sm/MeasurementValue'))"
foreach ($field in 'MeasuredValue.Value','MeasurementQualifier.Quality','MeasurementTimestamp') {
    $property = Invoke-RestMethod "$target/submodel-elements/$field"
    "$field = $($property.value)"
}
```

Expect `230`, `good` and the UTC timestamp sent above. Each MQTT message updates its own property.
