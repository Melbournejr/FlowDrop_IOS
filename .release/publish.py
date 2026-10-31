from pathlib import Path
import json,hashlib,subprocess,base64,tempfile,os,urllib.request,urllib.parse
root=Path('.release');assets=root/'1.11.0';repo=os.environ['GH_REPO'];tag='v1.11.0'
assert repo=='Melbournejr/FlowDrop_IOS'
def run(args):
 p=subprocess.run(args,capture_output=True,text=True,timeout=300)
 if p.returncode:raise RuntimeError((p.stderr or p.stdout)[:1800])
 return p.stdout.strip()
def api(method,route,body):
 with tempfile.NamedTemporaryFile('w',suffix='.json') as f:
  json.dump(body,f);f.flush();return json.loads(run(['gh','api','repos/'+repo+route,'--method',method,'--input',f.name]))
checks=json.loads((root/'checksums.json').read_text());expected={x['name']:x for x in checks}
for item in checks:
 data=(assets/item['name']).read_bytes();assert len(data)==item['size'] and hashlib.sha256(data).hexdigest()==item['sha256']
envelope=json.loads((assets/'latest.json').read_text());payload=envelope['payload'].encode('utf-8');(root/'payload.bin').write_bytes(payload);(root/'signature.bin').write_bytes(base64.b64decode(envelope['signature'],validate=True))
print(run(['openssl','dgst','-sha256','-verify',str(root/'update-public.pem'),'-signature',str(root/'signature.bin'),str(root/'payload.bin')]),flush=True)
manifest=json.loads(payload);assert manifest['app']=='FlowDrop' and manifest['schema']==1
for platform,name in [('windows','FlowDrop-Setup-1.11.0-Windows-x64.exe'),('android','FlowDrop-1.11.0-Android.apk')]:
 item=manifest['platforms'][platform];record=expected[name];assert item['version']=='1.11.0' and item['url']=='https://github.com/'+repo+'/releases/download/'+tag+'/'+name
 assert item['size']==record['size'] and item['sha256']==record['sha256']
 if platform=='android':assert item['versionCode']==12
probe=subprocess.run(['gh','api','repos/'+repo+'/releases/tags/'+tag],capture_output=True,text=True,timeout=60)
if probe.returncode==0:info=json.loads(probe.stdout)
else:
 assert '404' in probe.stderr,probe.stderr
 # Use the create response directly: draft listings may be cached immediately after creation.
 info=api('POST','/releases',{'tag_name':tag,'target_commitish':'ae85b16d9bf4d2f5d365d694b489af9234194099','name':'FlowDrop 1.11.0 — Thư mục nguyên cấu trúc','body':(root/'release-notes.md').read_text(),'draft':True,'prerelease':False})
assert info['tag_name']==tag and not info['prerelease'];rid=str(info['id']);existing={x['name']:x for x in info['assets']};assert not set(existing)-set(expected)
if not info['draft']:assert set(existing)==set(expected),'Published release is missing assets'
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
opener=urllib.request.build_opener(NoRedirect)
for name,item in expected.items():
 if name in existing:continue
 assert info['draft'],'Refusing to mutate a published release'
 endpoint=info['upload_url'].split('{',1)[0];parsed=urllib.parse.urlparse(endpoint)
 assert parsed.scheme=='https' and parsed.netloc=='uploads.github.com' and parsed.path=='/repos/'+repo+'/releases/'+rid+'/assets'
 request=urllib.request.Request(endpoint+'?name='+urllib.parse.quote(name),data=(assets/name).read_bytes(),method='POST',headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Content-Type':'application/octet-stream','Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
 with opener.open(request,timeout=300) as response:asset=json.load(response)
 assert asset['name']==name and asset['size']==item['size'];existing[name]=asset;print('Uploaded '+name,flush=True)
with tempfile.TemporaryDirectory() as download:
 for name,item in expected.items():
  local=Path(download)/name
  with local.open('wb') as output:
   p=subprocess.run(['gh','api','repos/'+repo+'/releases/assets/'+str(existing[name]['id']),'-H','Accept: application/octet-stream'],stdout=output,stderr=subprocess.PIPE,timeout=300)
  if p.returncode:raise RuntimeError(p.stderr.decode()[:1200])
  data=local.read_bytes();assert len(data)==item['size'] and hashlib.sha256(data).hexdigest()==item['sha256'],name
  print('Verified remote SHA256 '+name,flush=True)
if info['draft']:info=api('PATCH','/releases/'+rid,{'draft':False,'make_latest':'true'})
assert not info['draft'];print('Published '+info['html_url'],flush=True)
