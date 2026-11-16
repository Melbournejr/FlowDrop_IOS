# Private one-line stdin/stdout pipe. No production APK/update signing material.
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
function Trace-Vault([string]$stage) { if ($env:FLOWDROP_VAULT_DIAGNOSTICS -eq '1') { [Console]::Error.WriteLine('FLOWDROP_VAULT_STAGE='+$stage) } }
try {
  Trace-Vault 'assembly'
  [void][Reflection.Assembly]::Load('System.Security, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b03f5f7f11d50a3a')
  [void][Reflection.Assembly]::Load('System.Web.Extensions, Version=4.0.0.0, Culture=neutral, PublicKeyToken=31bf3856ad364e35')
  $json = [System.Web.Script.Serialization.JavaScriptSerializer]::new()
  $json.MaxJsonLength = 1048576
  Trace-Vault 'pipe-read'
  $inputData = $json.DeserializeObject([Console]::In.ReadLine())
  Trace-Vault 'pipe-ready'
  $entropy = [Text.Encoding]::UTF8.GetBytes('FlowDrop device transport vault v1')
  if ($inputData.operation -eq 'seal') {
    $raw = [Text.Encoding]::UTF8.GetBytes([string]$inputData.value)
    Trace-Vault 'protect'
    $sealed = [Security.Cryptography.ProtectedData]::Protect($raw,$entropy,[Security.Cryptography.DataProtectionScope]::CurrentUser)
    Trace-Vault 'protected'
    [Console]::Out.Write([Convert]::ToBase64String($sealed))
  } elseif ($inputData.operation -eq 'open') {
    Trace-Vault 'unprotect'
    $raw = [Security.Cryptography.ProtectedData]::Unprotect([Convert]::FromBase64String($inputData.value),$entropy,[Security.Cryptography.DataProtectionScope]::CurrentUser)
    [Console]::Out.Write([Text.Encoding]::UTF8.GetString($raw))
  } elseif ($inputData.operation -eq 'create') {
    # .NET 4.7.2+ CertificateRequest avoids Cert: provider/module initialization,
    # certificate-store writes, private key files and interactive PKI cmdlets.
    $rsa = $null; $certificate = $null
    try {
      Trace-Vault 'rsa-create'
      $rsa = [Security.Cryptography.RSACryptoServiceProvider]::new(2048)
      if ($rsa -is [Security.Cryptography.RSACryptoServiceProvider]) { $rsa.PersistKeyInCsp = $false }
      Trace-Vault 'rsa-created'
      $subject = [Security.Cryptography.X509Certificates.X500DistinguishedName]::new('CN='+$inputData.name)
      $request = [Security.Cryptography.X509Certificates.CertificateRequest]::new($subject,$rsa,[Security.Cryptography.HashAlgorithmName]::SHA256,[Security.Cryptography.RSASignaturePadding]::Pkcs1)
      [void]$request.CertificateExtensions.Add([Security.Cryptography.X509Certificates.X509BasicConstraintsExtension]::new($false,$false,0,$true))
      $usage = [Security.Cryptography.X509Certificates.X509KeyUsageFlags]::DigitalSignature -bor [Security.Cryptography.X509Certificates.X509KeyUsageFlags]::KeyEncipherment
      [void]$request.CertificateExtensions.Add([Security.Cryptography.X509Certificates.X509KeyUsageExtension]::new($usage,$true))
      Trace-Vault 'self-sign'
      $certificate = $request.CreateSelfSigned([DateTimeOffset]::Now.AddDays(-1),[DateTimeOffset]::Now.AddYears(5))
      Trace-Vault 'self-signed'
      $rng = [Security.Cryptography.RandomNumberGenerator]::Create(); $bytes = [byte[]]::new(32); $rng.GetBytes($bytes); $rng.Dispose()
      $password = [Convert]::ToBase64String($bytes)
      $result = @{pfx=[Convert]::ToBase64String($certificate.Export([Security.Cryptography.X509Certificates.X509ContentType]::Pfx,$password));passphrase=$password;certificate=[Convert]::ToBase64String($certificate.RawData)}
      Trace-Vault 'exported'
      [Console]::Out.Write($json.Serialize($result))
    } finally {
      if ($null -ne $certificate) { $certificate.Dispose() }
      if ($null -ne $rsa) { $rsa.Dispose() }
    }
  } else { throw 'Invalid vault operation' }
} catch {
  [Console]::Error.Write('FLOWDROP_VAULT_ERROR=' + $_.Exception.GetType().FullName + ':L' + $_.InvocationInfo.ScriptLineNumber + ':' + $_.FullyQualifiedErrorId)
  exit 1
}
