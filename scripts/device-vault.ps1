# Private stdin/stdout pipe only. No signing/update production material is accessed.
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
try {
Add-Type -AssemblyName System.Security
$inputData = [Console]::In.ReadToEnd() | ConvertFrom-Json
$entropy = [Text.Encoding]::UTF8.GetBytes('FlowDrop device transport vault v1')
if ($inputData.operation -eq 'seal') {
  $raw = [Text.Encoding]::UTF8.GetBytes([string]$inputData.value)
  [Console]::Out.Write([Convert]::ToBase64String([Security.Cryptography.ProtectedData]::Protect($raw,$entropy,[Security.Cryptography.DataProtectionScope]::CurrentUser)))
} elseif ($inputData.operation -eq 'open') {
  $raw = [Security.Cryptography.ProtectedData]::Unprotect([Convert]::FromBase64String($inputData.value),$entropy,[Security.Cryptography.DataProtectionScope]::CurrentUser)
  [Console]::Out.Write([Text.Encoding]::UTF8.GetString($raw))
} elseif ($inputData.operation -eq 'create') {
  $certificate = $null
  try {
    $certificate = New-SelfSignedCertificate -DnsName $inputData.name -CertStoreLocation Cert:\CurrentUser\My -KeyAlgorithm RSA -KeyLength 2048 -HashAlgorithm SHA256 -KeyExportPolicy Exportable -NotAfter (Get-Date).AddYears(5) -Type SSLServerAuthentication
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create(); $bytes = New-Object byte[] 32; $rng.GetBytes($bytes); $rng.Dispose()
    $password = [Convert]::ToBase64String($bytes)
    $result = @{pfx=[Convert]::ToBase64String($certificate.Export([Security.Cryptography.X509Certificates.X509ContentType]::Pfx,$password));passphrase=$password;certificate=[Convert]::ToBase64String($certificate.RawData)}
    [Console]::Out.Write(($result | ConvertTo-Json -Compress))
  } finally {
    if ($null -ne $certificate) { Remove-Item -LiteralPath ('Cert:\CurrentUser\My\'+$certificate.Thumbprint) -DeleteKey -Force }
  }
} else { throw 'Invalid vault operation' }

} catch {
  # Only public exception class/identifier. Never dump arguments or private stdout.
  [Console]::Error.Write('FLOWDROP_VAULT_ERROR=' + $_.Exception.GetType().FullName + ':' + $_.FullyQualifiedErrorId)
  exit 1
}
