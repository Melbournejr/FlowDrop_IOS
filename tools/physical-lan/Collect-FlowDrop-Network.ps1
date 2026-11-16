[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Root)
$ErrorActionPreference = 'Stop'
$rootItem = Get-Item -LiteralPath $Root
if (($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Refusing reparse point test root' }
$cursor = $rootItem
while ($null -ne $cursor) {
    if (($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Refusing linked parent' }
    $cursor = $cursor.Parent
}
$markerPath = Join-Path $rootItem.FullName '.flowdrop-lan-test.json'
$markerItem = Get-Item -LiteralPath $markerPath
if (($markerItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Unsafe marker' }
$marker = Get-Content -LiteralPath $markerPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($marker.schema -ne 1 -or $marker.run_id -notmatch '^[a-f0-9]{32}$') { throw 'Not an owned test workspace' }
$destination = Join-Path $rootItem.FullName 'network-environment.json'
if (Test-Path -LiteralPath $destination) { throw 'Network evidence already exists; preserve it and use a fresh test workspace' }
$result = [ordered]@{run_id=$marker.run_id; collected_utc=[DateTime]::UtcNow.ToString('o'); purpose='Read-only network diagnosis'; native_e2e='NOT VERIFIED'; physical_wifi='NOT VERIFIED'; security_settings_changed=$false}
try {
    $result['adapters'] = @(Get-NetIPConfiguration | ForEach-Object {
        [ordered]@{interface_index=$_.InterfaceIndex; interface_alias=$_.InterfaceAlias; ipv4=@($_.IPv4Address.IPAddress); gateway=@($_.IPv4DefaultGateway.NextHop); profile=$_.NetProfile.NetworkCategory.ToString()}
    })
    $result['adapters_status'] = 'PASS'
} catch { $result['adapters_status'] = 'BLOCKED'; $result['adapters_reason'] = 'Network cmdlet unavailable or denied; no settings changed' }
try {
    $result['firewall_profiles'] = @(Get-NetFirewallProfile | Select-Object Name,Enabled,DefaultInboundAction,DefaultOutboundAction)
    $result['flowdrop_rule_state'] = @(Get-NetFirewallRule -DisplayName '*FlowDrop*' -ErrorAction SilentlyContinue | Select-Object DisplayName,Enabled,Direction,Action,Profile)
    $result['firewall_observation_status'] = 'PASS'
} catch { $result['firewall_observation_status'] = 'BLOCKED'; $result['firewall_reason'] = 'Read-only firewall query denied; no rule changed' }
# No MAC address, SSID/password, environment dump, app profile, history or token is read.
$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $destination -Encoding UTF8
Write-Host 'Saved network-environment.json in the selected test workspace. No network/firewall setting was changed.'
exit 0
