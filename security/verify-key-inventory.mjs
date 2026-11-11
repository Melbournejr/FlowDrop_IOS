// Public-only verification; this script never reads private signing credentials.
import {readFile} from 'node:fs/promises';
import {createHash, createPublicKey, verify, X509Certificate} from 'node:crypto';
import assert from 'node:assert/strict';

const read = name => readFile(new URL(name, import.meta.url));
const bytes = await read('key-inventory.json');
const signature = (await read('key-inventory.json.sig')).toString('utf8').trim();
assert.match(signature, /^[A-Za-z0-9+/]{86}==$/);
const project = createPublicKey(await read('project-signing-public.pem'));
assert.equal(project.asymmetricKeyType, 'ed25519');
assert.ok(verify(null, Buffer.concat([Buffer.from('FlowDrop project manifest signature v1\0'), bytes]), project, Buffer.from(signature, 'base64')), 'Inventory signature is invalid.');
const inventory = JSON.parse(bytes);
assert.equal(inventory.schema, 1); assert.equal(inventory.app, 'FlowDrop');
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const publicDigest = key => digest(key.export({type: 'spki', format: 'der'}));
assert.equal(publicDigest(project), inventory.project.publicKeySha256);
assert.equal(publicDigest(createPublicKey(await read('update-signing-public.pem'))), inventory.updates.publicKeySha256);
assert.equal(digest(new X509Certificate(await read('android-signing-certificate.pem')).raw), inventory.android.certificateSha256);
console.log('Verified the signed public-key inventory and all three fingerprints.');
