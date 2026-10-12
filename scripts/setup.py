#!/usr/bin/env python3
"""Prepare pinned sources and the Linux x86-64 WASI compiler without system changes."""
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / "port.lock.json").read_text())
CACHE = ROOT / ".cache"

def run(*args):
    subprocess.run(args, check=True)

def setup():
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise SystemExit("The pinned build host is Linux x86-64; the resulting WASM runs on ARM iPad browsers.")
    CACHE.mkdir(exist_ok=True)
    source = CACHE / "blender"
    ref = LOCK["blender"]
    if not source.exists():
        run("git", "-c", "filter.lfs.smudge=", "-c", "filter.lfs.required=false", "clone",
            "--depth", "1", "--branch", ref["tag"], ref["repository"], str(source))
    head = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if head != ref["commit"]:
        raise SystemExit("Blender source differs from port.lock.json. Preserve it before fetching a new version.")
    changes = subprocess.check_output(["git", "-C", str(source), "status", "--porcelain"], text=True)
    if changes:
        raise SystemExit("Blender source has local changes; refusing to use or overwrite them.")
    sdk = LOCK["wasi_sdk"]
    archive = CACHE / "wasi-sdk.tar.gz"
    if not archive.exists():
        partial = archive.with_suffix(".download")
        with urllib.request.urlopen(sdk["url"], timeout=90) as response, partial.open("wb") as output:
            while block := response.read(1024 * 1024):
                output.write(block)
        partial.replace(archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != sdk["sha256"]:
        raise SystemExit("WASI SDK checksum mismatch; compiler will not be used.")
    compiler = CACHE / "wasi-sdk-25.0-x86_64-linux" / "bin" / "clang++"
    if not compiler.exists():
        with tarfile.open(archive) as bundle:
            bundle.extractall(CACHE, filter="data")
    run(str(compiler), "--version")
    print(f"Prepared Blender {ref['version']} at {head}; upstream sources unchanged.")

if __name__ == "__main__":
    setup()
