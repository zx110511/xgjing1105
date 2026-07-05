$ErrorActionPreference = "SilentlyContinue"
$base = "http://127.0.0.1:8778"
$endpoints = @(
    "/api/health",
    "/api/memory/stats",
    "/api/memory/",
    "/api/search/semantic?q=test",
    "/api/orchestrator/agents",
    "/api/orchestrator/v10/",
    "/api/orchestrator/v10/stats",
    "/api/orchestrator/v10/a2a/agent-cards",
    "/api/orchestrator/v10/a2a/stats",
    "/api/mcp/servers",
    "/api/mcp/",
    "/api/system/stats",
    "/api/ops/report",
    "/api/operations/summary",
    "/api/governance/status",
    "/api/config",
    "/api/llm/status",
    "/api/kg/topology?mode=sample&sample_rate=0.3&max_nodes=500",
    "/api/kg/metrics",
    "/api/kg/sss-audit",
    "/api/chat/conversations?limit=50",
    "/api/memory/layers/info",
    "/docs"
)
foreach ($ep in $endpoints) {
    $url = $base + $ep
    try {
        $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 20
        $code = $resp.StatusCode
        $body = $resp.Content
        if ($body.Length -gt 100) { $body = $body.Substring(0, 100) }
        $body = $body -replace "[\r\n]+", " "
        Write-Output ("{0}`t{1}`t{2}" -f $ep, $code, $body)
    }
    catch {
        $code = "ERR"
        if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
        $msg = $_.Exception.Message -replace "[\r\n]+", " "
        if ($msg.Length -gt 100) { $msg = $msg.Substring(0, 100) }
        Write-Output ("{0}`t{1}`t{2}" -f $ep, $code, $msg)
    }
}
