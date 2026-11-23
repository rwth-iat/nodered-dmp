$ErrorActionPreference = 'Stop'
foreach ($url in 'http://127.0.0.1:8081/submodels', 'http://127.0.0.1:1880/flows') {
    $deadline = (Get-Date).AddSeconds(90)
    while ($true) {
        try {
            Invoke-RestMethod $url -TimeoutSec 3 | Out-Null
            break
        } catch {
            if ((Get-Date) -ge $deadline) { throw "Service did not respond at $url" }
            Start-Sleep -Seconds 1
        }
    }
}
