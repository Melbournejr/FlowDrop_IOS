[CmdletBinding()]
param(
    [ValidateSet('Menu','Prepare','Environment','HashSource','Start','Stop','Compare','Report','AdbHash')]
    [string]$Action = 'Menu',
    [string]$Root,
    [ValidateSet('smoke','100m','1g','zip64')][string]$Profile = 'smoke',
    [switch]$AllowLarge,
    [ValidateSet('Windows-to-Android','Android-to-Windows','Windows-to-Windows','Android-to-Android')]
    [string]$Direction = 'Windows-to-Android',
    [ValidateSet('blackbox-production-1.13.0','test-artifact')][string]$Mode = 'blackbox-production-1.13.0',
    [ValidateSet('physical-wifi','physical-ethernet-wifi','isolated-virtual')][string]$Network = 'physical-wifi',
    [string]$ReceivedDir,
    [string]$Adb,
    [string]$Serial,
    [string]$RemoteDir
)
$ErrorActionPreference = 'Stop'
$script = Join-Path $PSScriptRoot 'flowdrop_lan.py'
$python = Get-Command python -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $python) { throw 'Install Python 3.12+ from python.org, then reopen PowerShell. No app or security setting was changed.' }
& $python.Source -c 'import sys; assert sys.version_info >= (3,12), "Python 3.12+ required"'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if ($Action -eq 'Menu') {
    Write-Host 'FlowDrop LAN verification: synthetic data, no app install/uninstall, no automatic deletion.'
    Write-Host '1 Prepare smoke data | 2 Check environment | 3 Start timing | 4 Stop timing | 5 Compare received folder | 6 Report | 7 Hash source'
    $choice = Read-Host 'Choose 1-7'
    $choices = @{'1'='Prepare';'2'='Environment';'3'='Start';'4'='Stop';'5'='Compare';'6'='Report';'7'='HashSource'}
    if (-not $choices.ContainsKey($choice)) { throw 'Invalid menu selection' }
    $Action = $choices[$choice]
    if (-not $Root) { $Root = Read-Host 'Dedicated test workspace (Prepare: NEW folder under an existing parent, e.g. C:\Users\you\Desktop\FlowDrop-LAN-01)' }
    if ($Action -eq 'Start') {
        Write-Host 'Directions: Windows-to-Android, Android-to-Windows, Windows-to-Windows, Android-to-Android'
        $Direction = Read-Host 'Direction'
    }
    if ($Action -eq 'Compare' -and -not $ReceivedDir) { $ReceivedDir = Read-Host 'Exact received FlowDrop-LAN-... folder (never the whole Downloads folder)' }
}
if (-not $Root) { throw 'Specify -Root with a dedicated synthetic workspace' }
$argsList = @('-X', 'utf8', $script, '--root', $Root)
switch ($Action) {
    'Prepare' { $argsList += @('prepare','--profile',$Profile); if ($AllowLarge) { $argsList += '--allow-large' } }
    'Environment' { $argsList += 'environment' }
    'HashSource' { $argsList += 'hash-source' }
    'Start' { $argsList += @('start','--direction',$Direction,'--mode',$Mode,'--network',$Network) }
    'Stop' { $argsList += 'stop' }
    'Compare' { if (-not $ReceivedDir) { throw 'Specify -ReceivedDir' }; $argsList += @('compare','--received-dir',$ReceivedDir) }
    'AdbHash' { if (-not $Adb -or -not $Serial -or -not $RemoteDir) { throw 'Specify trusted -Adb, explicit -Serial and exact synthetic -RemoteDir' }; $argsList += @('adb-hash','--adb',$Adb,'--serial',$Serial,'--remote-dir',$RemoteDir) }
    'Report' { $argsList += 'report' }
}
& $python.Source @argsList
exit $LASTEXITCODE
