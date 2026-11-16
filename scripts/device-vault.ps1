# Private one-line stdin/stdout pipe. No production APK/update signing material.
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
try {
  Add-Type -AssemblyName System.Security
  $inputData = [Console]::In.ReadLine() | ConvertFrom-Json
  $entropy = [Text.Encoding]::UTF8.GetBytes('FlowDrop device transport vault v1')
  if ($inputData.operation -eq 'seal') {
    $raw = [Text.Encoding]::UTF8.GetBytes([string]$inputData.value)
    [Console]::Out.Write([Convert]::ToBase64String([Security.Cryptography.ProtectedData]::Protect($raw,$entropy,[Security.Cryptography.DataProtectionScope]::CurrentUser)))
  } elseif ($inputData.operation -eq 'open') {
    $raw = [Security.Cryptography.ProtectedData]::Unprotect([Convert]::FromBase64String($inputData.value),$entropy,[Security.Cryptography.DataProtectionScope]::CurrentUser)
    [Console]::Out.Write([Text.Encoding]::UTF8.GetString($raw))
  } elseif ($inputData.operation -eq 'create') {
    # .NET 4.7.2+ CertificateRequest avoids Cert: provider/module initialization,
    # certificate-store writes, private key files and interactive PKI cmdlets.
    $rsa = $null; $certificate = $null
    try {
      $rsa = [Security.Cryptography.RSACryptoServiceProvider]::new(2048)
      if ($rsa -is [Security.Cryptography.RSACryptoServiceProvider]) { $rsa.PersistKeyInCsp = $false }
      $subject = [Security.Cryptography.X509Certificates.X500DistinguishedName]::new('CN='+$inputData.name)
      $request = [Security.Cryptography.X509Certificates.CertificateRequest]::new($subject,$rsa,[Security.Cryptography.HashAlgorithmName]::SHA256,[Security.Cryptography.RSASignaturePadding]::Pkcs1)
      $request.CertificateExtensions.Add([Security.Cryptography.X509Certificates.X509BasicConstraintsExtension]::new($false,$false,0,$true))
      $usage = [Security.Cryptography.X509Certificates.X509KeyUsageFlags]::DigitalSignature -bor [Security.Cryptography.X509Certificates.X509KeyUsageFlags]::KeyEncipherment
      $request.CertificateExtensions.Add([Security.Cryptography.X509Certificates.X509KeyUsageExtension]::new($usage,$true))
      $certificate = $request.CreateSelfSigned([DateTimeOffset]::Now.AddDays(-1),[DateTimeOffset]::Now.AddYears(5))
      $rng = [Security.Cryptography.RandomNumberGenerator]::Create(); $bytes = New-Object byte[] 32; $rng.GetBytes($bytes); $rng.Dispose()
      $password = [Convert]::ToBase64String($bytes)
      $result = @{pfx=[Convert]::ToBase64String($certificate.Export([Security.Cryptography.X509Certificates.X509ContentType]::Pfx,$password));passphrase=$password;certificate=[Convert]::ToBase64String($certificate.RawData)}
      [Console]::Out.Write(($result | ConvertTo-Json -Compress))
    } finally {
      if ($null -ne $certificate) { $certificate.Dispose() }
      if ($null -ne $rsa) { $rsa.Dispose() }
    }
  } else { throw 'Invalid vault operation' }
} catch {
  [Console]::Error.Write('FLOWDROP_VAULT_ERROR=' + $_.Exception.GetType().FullName + ':L' + $_.InvocationInfo.ScriptLineNumber + ':' + $_.FullyQualifiedErrorId)
  exit 1
}
