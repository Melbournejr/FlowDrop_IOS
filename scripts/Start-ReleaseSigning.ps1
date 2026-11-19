param([switch]$ValidateOnly)
$ErrorActionPreference = 'Stop'
# A Windows PowerShell child launched from pwsh can inherit Core-only module
# paths. Use this engine's built-in modules, without changing the user's profile.
if ($PSVersionTable.PSEdition -eq 'Desktop') {
  $env:PSModulePath = (Join-Path $PSHOME 'Modules') + ';' + (Join-Path $env:ProgramFiles 'WindowsPowerShell/Modules')
}
$root = $PSScriptRoot
if (-not (Test-Path (Join-Path $root 'production-build-proof.json'))) { throw 'Run the copy at the root of the downloaded signing kit.' }
function HashFile([string]$file) { (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() }
function QuoteArg([string]$value) { '"' + [regex]::Replace([regex]::Replace($value, '(\\*)"', '$1$1\"'), '(\\+)$', '$1$1') + '"' }
function RunPrivate([string]$exe, [string[]]$argv, [string[]]$secretInput = @(), [hashtable]$secretEnv = @{}) {
  $info = New-Object System.Diagnostics.ProcessStartInfo
  $info.FileName = $exe; $info.Arguments = (($argv | ForEach-Object { QuoteArg $_ }) -join ' ')
  $info.UseShellExecute = $false; $info.CreateNoWindow = $true; $info.RedirectStandardInput = $true
  $info.RedirectStandardOutput = $true; $info.RedirectStandardError = $true
  foreach ($name in @($info.EnvironmentVariables.Keys)) {
    if ($name -match 'TOKEN|SECRET|PASSWORD|CREDENTIAL|AUTH|NODE_OPTIONS|JAVA_TOOL_OPTIONS|JDK_JAVA_OPTIONS|_JAVA_OPTIONS|CLASSPATH') { $info.EnvironmentVariables.Remove($name) }
  }
  foreach ($name in $secretEnv.Keys) { $info.EnvironmentVariables[$name] = $secretEnv[$name] }
  $process = New-Object System.Diagnostics.Process; $process.StartInfo = $info
  try {
    # .NET Framework creates an AutoFlush StreamWriter during Start(), which
    # can emit Console.InputEncoding's preamble before BaseStream is accessed.
    $previousInputEncoding = [Console]::InputEncoding
    try { [Console]::InputEncoding = New-Object Text.UTF8Encoding($false); [void]$process.Start() }
    finally { [Console]::InputEncoding = $previousInputEncoding }
    $stdout = $process.StandardOutput.ReadToEndAsync(); $stderr = $process.StandardError.ReadToEndAsync()
    # Console.InputEncoding on Windows PowerShell can emit a BOM. Send exact
    # UTF-8 password lines without a preamble or a shell/argv conversion.
    $stdin = $process.StandardInput.BaseStream
    foreach ($line in $secretInput) {
      if ($line -match "[\r\n`0]") { throw 'Invalid password input.' }
      $bytes = [Text.Encoding]::UTF8.GetBytes($line + "`n"); $stdin.Write($bytes,0,$bytes.Length)
      [Array]::Clear($bytes,0,$bytes.Length)
    }
    $stdin.Flush(); $stdin.Close()
    if (-not $process.WaitForExit(180000)) { $process.Kill(); throw 'Signing tool timed out.' }
    $text = $stdout.Result; $ignoredError = $stderr.Result
    if ($process.ExitCode -ne 0) { throw 'Tool verification/signing failed. No key/password/log is uploaded. Check the selected original keys and passwords.' }
    return $text
  } finally { $process.Dispose(); foreach ($name in $secretEnv.Keys) { $info.EnvironmentVariables.Remove($name) } }
}
function Password([string]$prompt) {
  $secure = Read-Host $prompt -AsSecureString
  $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  try { [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer); $secure.Dispose() }
}
function ExternalKey([string]$prompt) {
  Add-Type -AssemblyName System.Windows.Forms
  $dialog = New-Object System.Windows.Forms.OpenFileDialog; $dialog.Title = $prompt; $dialog.CheckFileExists = $true
  try { if ($dialog.ShowDialog() -ne 'OK') { throw 'Cancelled; no release produced.' }; $file = [IO.Path]::GetFullPath($dialog.FileName) } finally { $dialog.Dispose() }
  if ($file.StartsWith($root + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Keep private keys outside the signing kit.' }
  if ((Get-Item -LiteralPath $file).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Select the original regular key file, not a link.' }
  return $file
}
$records = Get-Content -LiteralPath (Join-Path $root 'kit-files.json') -Raw | ConvertFrom-Json
foreach ($entry in $records) {
  if ([IO.Path]::IsPathRooted($entry.path) -or $entry.path -match '(^|[/\\])\.\.([/\\]|$)') { throw 'Unsafe kit path.' }
  $file = [IO.Path]::GetFullPath((Join-Path $root $entry.path))
  if (-not $file.StartsWith($root + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Kit path escapes its root.' }
  if ((HashFile $file) -ne $entry.sha256) { throw 'Kit checksum mismatch. Download the verified kit again.' }
}
$jreZip = Join-Path $root 'tools/windows-jre.zip'
if ((HashFile $jreZip) -ne '2332c0b4cff6bed722da3567c91d5e47568bcba863fa4945d0a8d6fc76158628') { throw 'Official JRE checksum mismatch.' }
$node = Join-Path $root 'tools/node.exe'
if ((HashFile $node) -ne '1c331340fa6cac5e4294725959070a143fa0507195a78ad77eed7943f719aac9') { throw 'Pinned Node checksum mismatch.' }
$session = Join-Path $root ('.signing-session-' + [guid]::NewGuid().ToString('N'))
[void](New-Item -ItemType Directory -Path $session)
try {
  Expand-Archive -LiteralPath $jreZip -DestinationPath (Join-Path $session 'jre')
  $java = Join-Path $session 'jre/jdk-21.0.13+9-jre/bin/java.exe'
  [void](RunPrivate $java @('-version')); [void](RunPrivate $node @('--version'))
  if ($ValidateOnly) { Write-Output 'PASS: kit checksums and actual Windows Java/Node execution. Production signing NOT VERIFIED.'; return }
  $keystore = ExternalKey 'Select ORIGINAL FlowDrop 1.13.0 Android keystore (never uploaded)'
  $rsa = ExternalKey 'Select ORIGINAL RSA update private key (never uploaded)'
  $storePassword = Password 'Android keystore password'
  $keyPassword = Password 'Android alias flowdrop password (Enter = same as store)'
  if ([string]::IsNullOrEmpty($keyPassword)) { $keyPassword = $storePassword }
  $rsaPassword = Password 'RSA private key password (Enter if unencrypted)'
  $artifacts = Join-Path $session 'artifacts'; [void](New-Item -ItemType Directory -Path $artifacts)
  Copy-Item -LiteralPath (Join-Path $root 'FlowDrop-Setup-1.14.0-Windows-x64.exe') -Destination $artifacts
  $apk = Join-Path $artifacts 'FlowDrop-1.14.0-Android.apk'; $signer = Join-Path $root 'tools/apksigner.jar'
  [void](RunPrivate $java @('-jar',$signer,'sign','--ks',$keystore,'--ks-key-alias','flowdrop','--ks-pass','stdin','--key-pass','stdin','--v1-signing-enabled','true','--v2-signing-enabled','true','--v3-signing-enabled','true','--out',$apk,(Join-Path $root 'FlowDrop-1.14.0-Android-UNSIGNED.apk')) @($storePassword,$keyPassword))
  $out = Join-Path $root 'Signed-release-1.14.0'
  $result = RunPrivate $node @((Join-Path $root 'scripts/make-release.mjs'),'--input',$artifacts,'--proof',(Join-Path $root 'production-build-proof.json'),'--key',$rsa,'--java',$java,'--apksigner',$signer,'--notes',(Join-Path $root 'Release-notes-1.14.0.md'),'--out',$out,'--skip-bundle') @() @{FLOWDROP_UPDATE_KEY_PASSWORD=$rsaPassword}
  $names = @('FlowDrop-1.14.0-Android.apk','FlowDrop-Setup-1.14.0-Windows-x64.exe','latest.json','SHA256SUMS-release.txt','Release-notes-1.14.0.md')
  $zip = Join-Path $root 'FlowDrop-1.14.0-SIGNED-RELEASE.zip'
  if (Test-Path -LiteralPath $zip) { throw 'Signed ZIP already exists; it was not overwritten.' }
  Compress-Archive -LiteralPath @($names | ForEach-Object { Join-Path $out $_ }) -DestinationPath $zip
  Write-Output $result
  Write-Output "Ready: $zip"
  Write-Output 'Upload only the five public files from Signed-release-1.14.0 to the GitHub Draft Release. Do not upload keys. Do not publish until release approval.'
} finally {
  $storePassword=$null; $keyPassword=$null; $rsaPassword=$null
  if ([IO.Path]::GetFullPath($session).StartsWith($root + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -and (Split-Path $session -Leaf) -match '^\.signing-session-[a-f0-9]{32}$') { Remove-Item -LiteralPath $session -Recurse -Force }
}
