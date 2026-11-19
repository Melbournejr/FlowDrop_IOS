param([Parameter(Mandatory=$true)][string]$Kit)
$ErrorActionPreference='Stop'
. (Join-Path $Kit 'Start-ReleaseSigning.ps1') -ValidateOnly
$node=Join-Path $Kit 'tools/node.exe'
$a='synthetic-a-'+[guid]::NewGuid().ToString('N');$b='synthetic-b-'+[guid]::NewGuid().ToString('N');$c='synthetic-c-'+[guid]::NewGuid().ToString('N')
$code='const c=require("node:crypto");let b="";process.stdin.setEncoding("utf8");process.stdin.on("data",x=>b+=x);process.stdin.on("end",()=>console.log(JSON.stringify({input:c.createHash("sha256").update(b.replace(/\r\n/g,"\n")).digest("hex"),secret:c.createHash("sha256").update(process.env.FLOWDROP_UPDATE_KEY_PASSWORD).digest("hex"),args:process.argv.slice(1)})));'
$value=RunPrivate $node @('-e',$code,'path with spaces','a"b') @($a,$b) @{FLOWDROP_UPDATE_KEY_PASSWORD=$c} | ConvertFrom-Json
function TextHash([string]$text) { $hash=[Security.Cryptography.SHA256]::Create();try{([BitConverter]::ToString($hash.ComputeHash([Text.Encoding]::UTF8.GetBytes($text)))).Replace('-','').ToLowerInvariant()}finally{$hash.Dispose()} }
$checks=@{stdin=($value.input -eq (TextHash ($a+"`n"+$b+"`n")));environment=($value.secret -eq (TextHash $c));spaces=($value.args[0] -eq 'path with spaces');quotes=($value.args[1] -eq 'a"b')}
if ($checks.Values -contains $false) { throw ('Private process checks failed: '+($checks | ConvertTo-Json -Compress)) }
$denied=$false
try { [void](RunPrivate $node @('-e','process.stderr.write(process.env.FLOWDROP_UPDATE_KEY_PASSWORD);process.exit(9)') @() @{FLOWDROP_UPDATE_KEY_PASSWORD=$c}) } catch { if ($_.ToString().Contains($c)) { throw 'Sensitive child error escaped redaction.' };$denied=$true }
if (-not $denied) { throw 'Nonzero child exit was masked.' }
Write-Output 'PASS: synthetic private stdin/env, quoted Windows paths, failure propagation and suppressed child secrets; no production key used.'
