import { readFile, mkdir, writeFile, rm, copyFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import assert from 'node:assert/strict';

const root = new URL('../', import.meta.url);
const dist = new URL('dist/', root);
const {version} = JSON.parse(await readFile(new URL('package.json', root), 'utf8'));
const release = new URL('releases/' + version + '/', root);
const manifest = JSON.parse(await readFile(new URL('manifest.json', release), 'utf8'));
assert.equal(manifest.version, version);
await rm(dist, { recursive: true, force: true });
await mkdir(new URL('.openai/', dist), { recursive: true });
await mkdir(new URL('downloads/', dist), { recursive: true });
const checksums = [];
for (const {name, sha256: expected, size} of manifest.files) {
  assert.ok(/^[A-Za-z0-9_.-]+$/.test(name));
  const bytes = await readFile(new URL(name, release));
  const digest = createHash('sha256').update(bytes).digest('hex');
  assert.equal(bytes.length, size, name + ': size mismatch');
  assert.equal(digest, expected, name + ': SHA256 mismatch');
  await writeFile(new URL('downloads/' + name, dist), bytes);
  checksums.push(digest + '  ' + name);
}
await writeFile(new URL('downloads/SHA256SUMS.txt', dist), checksums.join('\n') + '\n');
await copyFile(new URL('download-site/index.html', root), new URL('index.html', dist));
await copyFile(new URL('.openai/hosting.json', root), new URL('.openai/hosting.json', dist));
await writeFile(new URL('_headers', dist), '/downloads/*\n  Content-Disposition: attachment\n  X-Content-Type-Options: nosniff\n');
console.log('Download site built; both installers match verified SHA256 hashes.');
