// The signing key stays outside source control and outside the release bundle.
import {parseArgs} from 'node:util';
import {readFile,writeFile,mkdir,copyFile} from 'node:fs/promises';
import {createHash,sign} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
import {APP_VERSION,UPDATE_PUBLIC_KEY} from './release-config.mjs';
import {verifyRelease} from './secure-update.mjs';
const {values}=parseArgs({options:{key:{type:'string'},out:{type:'string'},'skip-bundle':{type:'boolean',default:false}}});
if(!values.key)throw new Error('Provide --key with the original PRIVATE update signing key path. Never publish the key.');
const directory=path.resolve(values.out||'releases/'+APP_VERSION);await mkdir(directory,{recursive:true});
const repo='https://github.com/Melbournejr/FlowDrop_IOS/releases/download/v'+APP_VERSION;
const manifest=await readFile('android/AndroidManifest.xml','utf8');
if(!manifest.includes('android:versionName="'+APP_VERSION+'"'))throw new Error('Android version differs from Windows release.');
const versionCode=Number(manifest.match(/android:versionCode="(\d+)"/)[1]);
const platforms={},checksums=[];
for(const [platform,name] of [['windows','FlowDrop-Setup-'+APP_VERSION+'-Windows-x64.exe'],['android','FlowDrop-'+APP_VERSION+'-Android.apk']]){
 const bytes=await readFile(path.join('artifacts',name)),sha256=createHash('sha256').update(bytes).digest('hex');await copyFile(path.join('artifacts',name),path.join(directory,name));
 platforms[platform]={version:APP_VERSION,url:repo+'/'+name,size:bytes.length,sha256,...(platform==='android'?{versionCode}:{})};checksums.push(sha256+'  '+name);
}
const payload=JSON.stringify({schema:1,app:'FlowDrop',notes:'Gia cố API Windows/Android, kiểm tra dữ liệu và thư mục, cập nhật Node LTS; thêm Chia sẻ một/nhiều file từ ứng dụng Android khác',platforms});
const key=await readFile(values.key),envelope={payload,signature:sign('RSA-SHA256',Buffer.from(payload),key).toString('base64')};
verifyRelease(envelope,UPDATE_PUBLIC_KEY);await writeFile(path.join(directory,'latest.json'),JSON.stringify(envelope,null,2)+'\n');
await writeFile(path.join(directory,'SHA256SUMS-release.txt'),checksums.join('\n')+'\n');
const notes=`# FlowDrop ${APP_VERSION}\n\n- Android: xuất hiện trong menu Chia sẻ của Thư viện và trình quản lý file; nhận một/nhiều file, giữ tên, xem trước và chọn thiết bị rồi mới gửi.\n- API tạo phiên gửi dùng khóa quyền riêng của ứng dụng; Windows không còn trả khóa qua HTTP chưa xác thực.\n- Chặn yêu cầu từ website khác, Host giả và HTTP nhập nhằng; giới hạn công việc xác minh đồng thời và đóng socket không hoạt động.\n- Kiểm tra mã, ID, tên, kiểu và dung lượng file; kiểm tra chỗ trống khi khôi phục thư mục.\n- Windows dùng Node 24.22.2 LTS đã xác minh checksum. Giữ khóa ký cập nhật và APK gốc.\n\nCài đè, không gỡ bản cũ. APK versionCode ${versionCode}. Đường truyền file LAN vẫn dùng HTTP, chưa mã hóa; dùng mạng tin cậy cho dữ liệu nhạy cảm. Xem SECURITY.md trong mã nguồn để biết phạm vi.\n`;

await writeFile(path.join(directory,'Release-notes-'+APP_VERSION+'.md'),notes);
const names=[...Object.values(platforms).map(x=>path.basename(x.url)),'latest.json','SHA256SUMS-release.txt','Release-notes-'+APP_VERSION+'.md'];
if(!values['skip-bundle'])execFileSync('python',['-c',`import zipfile,sys,pathlib\np=pathlib.Path(sys.argv[1])\nwith zipfile.ZipFile(p/sys.argv[2],'w',zipfile.ZIP_DEFLATED) as z:\n for n in sys.argv[3:]: z.write(p/n,n)`,directory,'FlowDrop-GitHub-Release-'+APP_VERSION+'.zip',...names]);
console.log(JSON.stringify({version:APP_VERSION,versionCode,platforms,bundle:values['skip-bundle']?null:path.join(directory,'FlowDrop-GitHub-Release-'+APP_VERSION+'.zip')},null,2));
