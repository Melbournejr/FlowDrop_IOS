$ErrorActionPreference = 'Stop'
$program = Join-Path $PSScriptRoot 'runtime\node.exe'
if (!(Test-Path -LiteralPath $program)) { throw 'FlowDrop runtime not found.' }
# Only the bundled runtime may accept traffic from the local subnet.
foreach ($protocol in @('TCP', 'UDP')) {
  $name = 'FlowDrop-LAN-' + $protocol + '-' + [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($program)).Replace('=', '')
  Get-NetFirewallRule -Name $name -ErrorAction SilentlyContinue | Remove-NetFirewallRule
  New-NetFirewallRule -Name $name -DisplayName ('FlowDrop Wi-Fi ' + $protocol) -Direction Inbound -Program $program -Action Allow -Protocol $protocol -RemoteAddress LocalSubnet -Profile Private,Public | Out-Null
}
