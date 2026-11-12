import {timingSafeEqual} from 'node:crypto';
export const sameSecret=(input,expected)=>typeof input==='string'&&typeof expected==='string'&&input.length===expected.length&&Buffer.byteLength(input)===Buffer.byteLength(expected)&&timingSafeEqual(Buffer.from(input),Buffer.from(expected));
export const loopback=address=>['127.0.0.1','::1','::ffff:127.0.0.1'].includes(address);
export function validateMetadata(value,code){
  if(!value||typeof value!=='object'||value.code!==code||!Array.isArray(value.files)||!value.files.length)throw new Error('Danh sách file hoặc mã trả về không hợp lệ.');
  const seen=new Set();let total=0;
  for(const f of value.files){
    if(!f||typeof f.id!=='string'||!/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(f.id)||seen.has(f.id)||typeof f.name!=='string'||!f.name.trim()||f.name.length>255||/[\x00-\x1f\x7f]/.test(f.name)||!Number.isSafeInteger(f.size)||f.size<0||!Number.isSafeInteger(total+f.size)||f.type!==undefined&&(typeof f.type!=='string'||f.type.length>150||/[\x00-\x1f\x7f]/.test(f.type)))throw new Error('Thông tin file không hợp lệ.');
    total+=f.size;seen.add(f.id);
  }
  return value;
}
export function browserRequestAllowed(headers,origin){return (!headers.origin||headers.origin===origin)&&(!headers['sec-fetch-site']||['same-origin','none'].includes(headers['sec-fetch-site']));}
