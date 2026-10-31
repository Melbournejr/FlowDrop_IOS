from pathlib import Path
import json,hashlib,subprocess,base64,tempfile,os
root=Path('.release');assets=root/'1.10.0';repo=os.environ['GH_REPO'];tag='v1.10.0'
assert repo=='Melbournejr/FlowDrop_IOS'
def run(args):
 p=subprocess.run(args,capture_output=True,text=True,timeout=300)
 if p.returncode:raise RuntimeError((p.stderr or p.stdout)[:2000])
 return p.stdout.strip()
checks=json.loads((root/'checksums.json').read_text())
for item in checks:
 f=assets/item['name'];assert f.stat().st_size==item['size'];assert hashlib.sha256(f.read_bytes()).hexdigest()==item['sha256']
envelope=json.loads((assets/'latest.json').read_text());payload=envelope['payload'].encode('utf-8');(root/'payload.bin').write_bytes(payload);(root/'signature.bin').write_bytes(base64.b64decode(envelope['signature'],validate=True))
print(run(['openssl','dgst','-sha256','-verify',str(root/'update-public.pem'),'-signature',str(root/'signature.bin'),str(root/'payload.bin')]),flush=True)
manifest=json.loads(payload);assert manifest['app']=='FlowDrop' and manifest['schema']==1
for platform,name in [('windows','FlowDrop-Setup-1.10.0-Windows-x64.exe'),('android','FlowDrop-1.10.0-Android.apk')]:
 item=manifest['platforms'][platform];record=next(x for x in checks if x['name']==name)
 assert item['version']=='1.10.0' and item['url']=='https://github.com/'+repo+'/releases/download/'+tag+'/'+name
 assert item['size']==record['size'] and item['sha256']==record['sha256']
 if platform=='android':assert item['versionCode']==11
info=json.loads(run(['gh','api','repos/'+repo+'/releases/tags/'+tag]));assert info['tag_name']==tag and not info['prerelease']
expected={x['name']:x for x in checks};existing={x['name']:x for x in info['assets']};assert not set(existing)-set(expected)
if not info['draft']:assert set(existing)==set(expected),'An already published release is missing assets'
for name,item in expected.items():
 if name not in existing:
  assert info['draft'],'Refusing to mutate a published release'
  run(['gh','release','upload',tag,'--repo',repo,str(assets/name)])
  print('Uploaded '+name,flush=True)
with tempfile.TemporaryDirectory() as download:
 for name,item in expected.items():
  run(['gh','release','download',tag,'--repo',repo,'--pattern',name,'--dir',download])
  data=(Path(download)/name).read_bytes();assert len(data)==item['size'] and hashlib.sha256(data).hexdigest()==item['sha256'],name
  print('Verified remote SHA256 '+name,flush=True)
if info['draft']:run(['gh','release','edit',tag,'--repo',repo,'--draft=false','--latest','--notes-file',str(root/'release-notes.md')])
latest=json.loads(run(['gh','api','repos/'+repo+'/releases/latest']));assert latest['tag_name']==tag and not latest['draft']
print('Published '+latest['html_url'],flush=True)
