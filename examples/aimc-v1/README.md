# AIMC 1.0 · MQTT to OperationalData

Complete the [common setup](../README.md), then run the following from the repository root.

## Import and deploy

Import once per fresh BaSyx container. Reuse the same repository-root PowerShell session.

```powershell
$server = 'http://127.0.0.1:8081'
New-Item -ItemType Directory -Force tmp | Out-Null
curl.exe -f -sS -H 'Accept: application/json' -F 'file=@examples/aimc-v1/AID_AIMC_Example.aasx;type=application/asset-administration-shell-package' "$server/upload"
if ($LASTEXITCODE) { throw 'AASX upload failed.' }
$aimc = uv run python -c "from nodered_dmp.aas.client import id_to_url; print(id_to_url('$server', 'https://example.com/ids/sm/AssetInterfacesMappingConfiguration'))"
uv run python main.py --store tmp/aimc-v1-store.json sync-aas --server $server --aimc-url $aimc
if ($LASTEXITCODE) { throw 'DMP command failed.' }
uv run python main.py --store tmp/aimc-v1-store.json build-flow --label 'AIMC 1.0 - OperationalData' --output tmp/aimc-v1-flow.json --nodered-server http://127.0.0.1:1880
if ($LASTEXITCODE) { throw 'DMP command failed.' }
```

## Verify live data

```powershell
docker compose @compose exec -T mqtt mosquitto_pub -h 127.0.0.1 -q 2 -t /sampleDevice/properties/voltage -m 230
$target = uv run python -c "from nodered_dmp.aas.client import id_to_url; print(id_to_url('$server', 'https://example.com/ids/sm/OperationalData'))"
(Invoke-RestMethod "$target/submodel-elements/MQTT_Data.voltage").value
```

The final command should return `230`.
