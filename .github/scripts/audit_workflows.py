#!/usr/bin/env python3
"""Offline repository checks; failures identify paths without printing secret values."""
from pathlib import Path
import re
import subprocess
import sys

PIN = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
DOCKER_PIN = re.compile(r"^docker://[\w./:-]+@sha256:[0-9a-f]{64}$")
USES = re.compile(r"^\s*(?:-\s*)?uses:\s*['\"]?([^\s#'\"]+)", re.MULTILINE)
PRIVATE_KEY = re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----")
TOKEN = re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})\b")


def audit_workflow(text):
    errors = []
    if re.search(r"^\s*pull_request_target\s*:", text, re.MULTILINE):
        errors.append("pull_request_target is not permitted")
    if re.search(r"^\s*permissions\s*:\s*['\"]?write-all", text, re.MULTILINE):
        errors.append("write-all token permissions are not permitted")
    if not re.search(r"^permissions:\s*$", text, re.MULTILINE):
        errors.append("explicit workflow token permissions are required")
    root_permissions = re.search(r"^permissions:\s*\n((?:[ \t]+[^\n]*\n|\n)*)", text, re.MULTILINE)
    if root_permissions and re.search(r"^\s+[\w-]+:\s*write\b", root_permissions.group(1), re.MULTILINE):
        errors.append("write permissions must be scoped to individual jobs")
    for match in USES.finditer(text):
        action = match.group(1)
        if not (action.startswith("./") and ".." not in action.split("/") or PIN.fullmatch(action) or DOCKER_PIN.fullmatch(action)):
            errors.append("external action is not pinned to a full commit SHA: " + action)
        if action.startswith("actions/checkout@"):
            tail = text[match.end():]
            boundary = re.search(r"\n\s*-\s+(?:name|uses|run|id):", tail)
            step = tail[:boundary.start()] if boundary else tail
            if not re.search(r"persist-credentials:\s*['\"]?false\b", step):
                errors.append("checkout must disable persisted credentials")
    return errors


def audit_file(path):
    errors = []
    if path.suffix.lower() in {".key", ".p12", ".pfx", ".jks", ".keystore"} or path.name.startswith(".env") and path.name not in {".env.example", ".env.sample"}:
        errors.append("credential or signing file must not be tracked")
    # Stream instead of loading large binaries. An overlap catches split markers.
    with path.open("rb") as stream:
        tail = b""
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            data = tail + block
            if PRIVATE_KEY.search(data):
                errors.append("private key material detected")
                break
            if TOKEN.search(data):
                errors.append("GitHub credential pattern detected")
                break
            tail = data[-256:]
    if path.parent.name == "workflows" and path.suffix in {".yml", ".yaml"}:
        errors.extend(audit_workflow(path.read_text(encoding="utf-8")))
    return errors


def main():
    files = subprocess.check_output(["git", "ls-files", "-z"]).decode().split("\0")
    failures = 0
    for name in filter(None, files):
        path = Path(name)
        if not path.is_file() or path.is_symlink():
            continue
        for error in audit_file(path):
            print(f"{name}: {error}", file=sys.stderr)
            failures += 1
    if failures:
        return 1
    print("Tracked files and workflow security policy passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
