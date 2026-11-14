import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import shutil
import stat
import tarfile
import zipfile

MARKER = '.flowdrop-2c2-owned'
PURPOSE = 'FlowDrop 2C2 TEST ONLY v1'
REPO = Path(__file__).resolve().parents[2]


class Blocked(RuntimeError):
    pass


def digest(path, algorithm='sha256'):
    h = hashlib.new(algorithm)
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def owned_root(value):
    path = Path(value).absolute()
    if '..' in path.parts or path.is_symlink():
        raise Blocked('Unsafe build root')
    resolved = path.resolve()
    if resolved in (Path('/'), Path.home().resolve(), REPO) or resolved in REPO.parents:
        raise Blocked('Build root cannot be home, filesystem root or source ancestor')
    path.mkdir(parents=True, exist_ok=True)
    marker = path / MARKER
    if marker.is_symlink():
        raise Blocked('Symlink ownership marker')
    if not marker.exists():
        if any(path.iterdir()):
            raise Blocked('Refusing an existing unowned build root')
        marker.write_text(PURPOSE)
    if marker.read_text() != PURPOSE:
        raise Blocked('Build root has another purpose')
    return path.resolve()


def require_owned(path):
    path = Path(path).absolute()
    marker = path / MARKER
    if path.is_symlink() or marker.is_symlink() or not marker.is_file() or marker.read_text() != PURPOSE:
        raise Blocked('Operation requires an owned 2C2 root')
    return path.resolve()


def child_path(root, value):
    root = require_owned(root)
    value = Path(value).absolute()
    if '..' in value.parts or value == root or not value.is_relative_to(root):
        raise Blocked('Path escapes build root')
    current = value
    while current != root:
        if current.is_symlink():
            raise Blocked('Symlink in build path')
        current = current.parent
    if not value.resolve().is_relative_to(root):
        raise Blocked('Resolved path escapes build root')
    return value


def remove_child(root, value):
    value = child_path(root, value)
    if value.is_dir():
        shutil.rmtree(value)
    elif value.exists():
        value.unlink()


def fresh_child(root, value):
    value = child_path(root, value)
    remove_child(root, value)
    value.mkdir(parents=True)
    return value


def archive_name(value, strip=0):
    value = value.rstrip('/')
    while value.startswith('./'):
        value = value[2:]
    if value in ('', '.'):
        return None
    p = PurePosixPath(value)
    if p.is_absolute() or any(c in value for c in '\\:\x00\r\n') or '..' in p.parts:
        raise Blocked('Unsafe archive member path')
    parts = p.parts[strip:]
    return PurePosixPath(*parts) if parts else None


def safe_extract_zip(archive, destination, strip=0):
    destination = Path(destination)
    if destination.is_symlink():
        raise Blocked('Symlink extraction destination')
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        plan, names, total = [], set(), 0
        for entry in z.infolist():
            name = archive_name(entry.filename, strip)
            if name is None:
                continue
            mode = entry.external_attr >> 16
            if stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR) or entry.flag_bits & 1:
                raise Blocked('Archive link/special/encrypted member')
            key = str(name).casefold()
            if key in names:
                raise Blocked('Duplicate archive member')
            names.add(key)
            total += entry.file_size
            if total > 3 * 2**30 or entry.file_size > 512 * 2**20:
                raise Blocked('Tool archive size limit')
            plan.append((entry, name, mode))
        for entry, name, mode in plan:
            target = destination / str(name)
            if not target.resolve().is_relative_to(destination.resolve()) or target.is_symlink():
                raise Blocked('Extraction escapes destination')
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                raise Blocked('Archive overwrites existing file')
            with z.open(entry) as source, target.open('xb') as out:
                shutil.copyfileobj(source, out, 1024 * 1024)
            target.chmod(0o755 if mode & 0o111 else 0o644)


def safe_extract_tar(tar, destination, strip=0, debian=False):
    """Validate before writing; only internal toolchain links may be materialized."""
    destination = Path(destination)
    if destination.is_symlink():
        raise Blocked('Symlink extraction destination')
    destination.mkdir(parents=True, exist_ok=True)
    plan, seen, links, total = [], set(), set(), 0
    for entry in tar.getmembers():
        name = archive_name(entry.name, strip)
        if name is None:
            continue
        if not (entry.isfile() or entry.isdir() or entry.issym() or entry.islnk()):
            raise Blocked('Special file in toolchain archive')
        if str(name) in seen:
            raise Blocked('Duplicate tar path')
        seen.add(str(name))
        total += entry.size
        if total > 3 * 2**30 or entry.size > 512 * 2**20:
            raise Blocked('Tool archive size limit')
        target_name = None
        if entry.issym() or entry.islnk():
            raw = entry.linkname
            if raw.startswith('/'):
                if not debian or not raw.startswith('/usr/'):
                    raise Blocked('External absolute archive link')
                raw = raw[1:]
                target_name = archive_name(raw)
            elif entry.islnk():
                target_name = archive_name(raw, strip)
            else:
                normalized = posixpath.normpath(str(name.parent / raw))
                target_name = archive_name(normalized)
            if target_name is None:
                raise Blocked('Invalid toolchain link')
            links.add(name)
        plan.append((entry, name, target_name))
    for _, name, _ in plan:
        if any(parent in links for parent in name.parents):
            raise Blocked('Archive writes through link')
    for entry, name, _ in plan:
        target = destination / str(name)
        if target.is_symlink() or not target.resolve().is_relative_to(destination.resolve()):
            raise Blocked('Toolchain path collision/escape')
        if entry.isdir():
            target.mkdir(parents=True, exist_ok=True)
        elif entry.isfile():
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                # Separate authenticated Debian packages can ship identical documentation.
                with tar.extractfile(entry) as source:
                    content = source.read()
                if target.read_bytes() != content:
                    raise Blocked('Conflicting toolchain package files')
                continue
            with tar.extractfile(entry) as source, target.open('xb') as out:
                shutil.copyfileobj(source, out, 1024 * 1024)
            target.chmod(0o755 if entry.mode & 0o111 else 0o644)
    for entry, name, link in plan:
        if link is None:
            continue
        target, source = destination / str(name), destination / str(link)
        if not source.resolve().is_relative_to(destination.resolve()):
            raise Blocked('Toolchain link escapes root')
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() or target.is_symlink():
            if target.is_symlink() and target.resolve() == source.resolve():
                continue
            raise Blocked('Conflicting toolchain link')
        if entry.islnk():
            if not source.is_file():
                raise Blocked('Missing hardlink target')
            shutil.copyfile(source, target)
            target.chmod(0o755 if entry.mode & 0o111 else 0o644)
        else:
            target.symlink_to(os.path.relpath(source, target.parent))
