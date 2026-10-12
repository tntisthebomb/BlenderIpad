#!/usr/bin/env python3
"""Prepare the full-port toolchain and a guarded, patched stable source copy."""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache"
LOCK = json.loads((ROOT / "browser-port.lock.json").read_text())
BLENDER = json.loads((ROOT / LOCK["blender_lock"]).read_text())["blender"]

def run(*args, **kwargs):
    subprocess.run(list(map(str, args)), check=True, **kwargs)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def toolchain():
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise SystemExit("The current build recipe requires Linux x86-64.")
    CACHE.mkdir(exist_ok=True)
    sdk = CACHE / "emsdk"
    if not sdk.exists():
        run("git", "clone", "--depth", "1", "--branch", LOCK["emsdk"]["version"],
            LOCK["emsdk"]["repository"], sdk)
    head = subprocess.check_output(["git", "-C", str(sdk), "rev-parse", "HEAD"], text=True).strip()
    if head != LOCK["emsdk"]["commit"]:
        raise SystemExit("SDK source does not match the pinned commit; refusing to overwrite it.")
    if subprocess.check_output(["git", "-C", str(sdk), "status", "--porcelain"], text=True):
        raise SystemExit("SDK has local changes; preserve them before preparing the toolchain.")
    if not (sdk / "upstream/emscripten/emcc").exists():
        run(sys.executable, sdk / "emsdk.py", "install", LOCK["emsdk"]["version"], cwd=sdk)
    if not (sdk / ".emscripten").exists():
        run(sys.executable, sdk / "emsdk.py", "activate", LOCK["emsdk"]["version"], cwd=sdk,
            stdout=subprocess.DEVNULL)
    tools = CACHE / "python"
    if not (tools / "bin/cmake").exists() or not (tools / "bin/ninja").exists():
        if not (tools / "bin/python").exists():
            run(sys.executable, "-m", "venv", tools)
        run(tools / "bin/python", "-m", "pip", "install", "--cache-dir", CACHE / "pip",
            "cmake==" + LOCK["cmake"], "ninja==" + LOCK["ninja"])
    env = dict(os.environ)
    env.update({"EMSDK": str(sdk), "EM_CONFIG": str(sdk / ".emscripten"),
                "EMCC_CORES": "4", "PATH": str(tools / "bin") + os.pathsep +
                str(sdk / "upstream/emscripten") + os.pathsep + env["PATH"]})
    version_output = subprocess.check_output([str(sdk / "upstream/emscripten/emcc"), "--version"],
                                             env=env, text=True)
    if not re.search(r"\b" + re.escape(LOCK["emsdk"]["version"]) + r"\b", version_output):
        raise SystemExit("The installed compiler differs from the pinned Emscripten release.")
    return env

def prepare_source(materialize_assets=False):
    pristine = CACHE / "blender"
    if not pristine.exists():
        run("git", "clone", "--depth", "1", "--branch", BLENDER["tag"], BLENDER["repository"], pristine,
            env={**os.environ, "GIT_LFS_SKIP_SMUDGE": "1"})
    head = subprocess.check_output(["git", "-C", str(pristine), "rev-parse", "HEAD"], text=True).strip()
    if head != BLENDER["commit"]:
        raise SystemExit("Pristine Blender source differs from the release pin.")
    if subprocess.check_output(["git", "-C", str(pristine), "status", "--porcelain"], text=True):
        raise SystemExit("Pristine Blender source contains changes; refusing to replace them.")
    source = CACHE / "blender-browser"
    if not source.exists():
        shutil.copytree(pristine, source, ignore=shutil.ignore_patterns(".git"))
    metadata_path = source / ".port-source.json"
    previous = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
    if previous and previous.get("commit") != head:
        raise SystemExit("Prepared source belongs to another release; preserve it before updating.")
    patch = ROOT / "patches/blender-5.2.2-ghost-web.patch"
    patched_paths = ["CMakeLists.txt", "intern/ghost/CMakeLists.txt", "intern/ghost/intern/GHOST_ISystem.cc"]
    with tempfile.TemporaryDirectory(prefix="ghost-patch-", dir=CACHE) as temporary:
        expected = Path(temporary)
        for relative in patched_paths:
            (expected / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(pristine / relative, expected / relative)
        run("patch", "--batch", "-p1", "-i", patch, cwd=expected, stdout=subprocess.DEVNULL)
        generated = {relative: (expected / relative).read_bytes() for relative in patched_paths}
    for path in (ROOT / "native/browser").glob("GHOST_*"):
        generated["intern/ghost/intern/" + path.name] = path.read_bytes()
    startup_relative = "release/datafiles/startup.blend"
    pointer = subprocess.check_output(["git", "-C", str(pristine), "show", "HEAD:" + startup_relative], text=True)
    asset_oid = re.search(r"oid sha256:([a-f0-9]+)", pointer).group(1)
    # Check all copied inputs. Only generated files and the verified LFS asset may differ.
    for origin in pristine.rglob("*"):
        relative = origin.relative_to(pristine).as_posix()
        if ".git" in origin.relative_to(pristine).parts or not origin.is_file() or relative in generated:
            continue
        actual = source / relative
        if not actual.is_file():
            raise SystemExit(f"Prepared source file is missing: {relative}")
        actual_hash = digest(actual)
        if actual_hash != digest(origin) and not (relative == startup_relative and actual_hash == asset_oid):
            raise SystemExit(f"Prepared source has local edits: {relative}; they will not be overwritten.")
    for relative, data in generated.items():
        actual = source / relative
        permitted = {hashlib.sha256(data).hexdigest(), previous.get("generated", {}).get(relative)}
        original = pristine / relative
        if original.exists():
            permitted.add(digest(original))
        if actual.exists() and digest(actual) not in permitted:
            raise SystemExit(f"Generated platform source has local edits: {relative}")
        actual.parent.mkdir(parents=True, exist_ok=True)
        actual.write_bytes(data)
    if materialize_assets and digest(source / startup_relative) != asset_oid:
        # Blender's public LFS objects are hosted upstream, not in the GitHub mirror.
        endpoint = "https://projects.blender.org/blender/blender.git/info/lfs"
        run("git", "-C", pristine, "-c", "lfs.url=" + endpoint, "-c", "lfs." + endpoint + ".access=none",
            "lfs", "fetch", "--include=" + startup_relative, "origin", "HEAD",
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
        object_path = pristine / ".git/lfs/objects" / asset_oid[:2] / asset_oid[2:4] / asset_oid
        if not object_path.exists() or digest(object_path) != asset_oid:
            raise SystemExit("Startup LFS object could not be verified against Blender's SHA256.")
        shutil.copyfile(object_path, source / startup_relative)
    metadata_path.write_text(json.dumps({"commit": head, "patch_sha256": digest(patch),
        "generated": {name: hashlib.sha256(data).hexdigest() for name, data in generated.items()},
        "startup_verified": digest(source / startup_relative) == asset_oid}, indent=2) + "\n")
    return source

if __name__ == "__main__":
    toolchain()
    source = prepare_source(materialize_assets="--assets" in sys.argv)
    print("Prepared stable browser source:", source)
