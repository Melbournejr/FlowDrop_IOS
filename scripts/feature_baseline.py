"""Reviewed 1.14 source changes, layered over immutable 1.13 audit manifests.

No historical evidence is rewritten. Every changed/new source byte is pinned;
application/update identities, dependencies, assets and iOS retain base checks.
"""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import subprocess

REPO = Path(__file__).resolve().parents[1]
BASE = 'ebaa66049464fe20e3ba22b1031df2f62fe124c7'
MANIFEST = REPO / 'docs/development/1.14.0/SOURCE-BASELINE.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


@lru_cache(maxsize=1)
def approved():
    doc = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if doc['base'] != BASE or doc['version'] != '1.14.0' or doc['schema'] != 1:
        raise RuntimeError('Unrecognized feature source baseline')
    rows = {}
    for row in doc['files']:
        name = row['path']
        if name in rows or '..' in Path(name).parts or Path(name).is_absolute() or (name.startswith(('ios/', 'security/')) or name.startswith('.github/workflows/') and name not in ['.github/workflows/native-build-verification.yml', '.github/workflows/native-regression.yml', '.github/workflows/native-runtime-verification.yml', '.github/workflows/native-release-preparation.yml']):
            raise RuntimeError('Unapproved feature source path')
        rows[name] = row
    return rows


def expected_sha(name, historical):
    row = approved().get(name)
    if row is None:
        return historical
    if row['base_sha256'] != historical:
        raise RuntimeError('Feature policy disagrees with historical baseline: ' + name)
    return row['sha256']


def verify_feature():
    subprocess.run(['git', 'merge-base', '--is-ancestor', BASE, 'HEAD'], cwd=REPO, check=True, stdout=subprocess.DEVNULL)
    for name, row in approved().items():
        file = REPO / name
        if file.is_symlink() or not file.is_file() or sha(file.read_bytes()) != row['sha256']:
            raise RuntimeError('Feature source bytes changed: ' + name)
    # No transitive dependency or runtime pin movement is authorized by this feature.
    old = json.loads(subprocess.check_output(['git', 'show', BASE + ':package-lock.json'], cwd=REPO))
    actual = json.loads((REPO / 'package-lock.json').read_text())
    actual['version'] = old['version']
    actual['packages']['']['version'] = old['packages']['']['version']
    if actual != old:
        raise RuntimeError('Application dependency lock changed')
    for name in ['desktop/windows/runtime.json', 'desktop/windows/FlowDrop.ico']:
        if (REPO / name).read_bytes() != subprocess.check_output(['git', 'show', BASE + ':' + name], cwd=REPO):
            raise RuntimeError('Frozen runtime/icon changed')
    for name in ['scripts/release-config.mjs', 'android/src/app/flowdrop/mobile/ReleaseConfig.java']:
        source = (REPO / name).read_text()
        original = subprocess.check_output(['git', 'show', BASE + ':' + name], cwd=REPO).decode()
        if source.replace('1.14.0', '1.13.0').replace('VERSION_CODE=15', 'VERSION_CODE=14') != original:
            raise RuntimeError('Update feed/public signing identity changed')
    pin = '65cbed4feb375d2c3c2eb94e668bd7aaee7ce5b24f436887873a6fa11719f97f'
    if json.loads((REPO / 'security/key-inventory.json').read_text())['android']['certificateSha256'] != pin:
        raise RuntimeError('Production APK signing identity changed')
    name = 'android/src/app/flowdrop/mobile/AppUpdates.java'
    if (REPO / name).read_bytes() != subprocess.check_output(['git', 'show', BASE + ':' + name], cwd=REPO):
        raise RuntimeError('Installed Android signer verification changed')
    return {'feature_version': '1.14.0', 'feature_base': BASE, 'feature_files_checked': len(approved()),
            'production_source_equivalence': '1.14.0 pinned source; intentionally differs from 1.13.0'}
