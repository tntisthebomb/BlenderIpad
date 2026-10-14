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
    # Asyncify expands the complete editor substantially. Parallel Binaryen
    # function passes exceed an 8 GiB builder's memory; serialize those passes
    # without changing optimization, assertions or suspension instrumentation.
    env["BINARYEN_CORES"] = "1"
    # Keep optimization and Asyncify IR in separate processes on 8 GiB builders.
    # The pinned SDK remains pristine; other Binaryen tools use direct symlinks.
    binaryen = CACHE / "binaryen-memory/bin"
    binaryen.mkdir(parents=True, exist_ok=True)
    wrapper = ROOT / "scripts/binaryen_memory.py"
    wrapper.chmod(0o755)
    for executable in (sdk / "upstream/bin").iterdir():
        if executable.is_file():
            target = wrapper if executable.name == "wasm-opt" else executable
            link = binaryen / executable.name
            if not link.exists():
                link.symlink_to(target)
    env["EM_BINARYEN_ROOT"] = str(binaryen.parent)
    env["BLENDER_BINARYEN_WASM_OPT"] = str(sdk / "upstream/bin/wasm-opt")
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
    patches = [ROOT / "patches/blender-5.2.2-ghost-web.patch",
               *sorted((ROOT / "patches").glob("blender-5.2.2-browser-*.patch"))]
    patched_paths = sorted({line[6:] for patch in patches for line in patch.read_text().splitlines()
                            if line.startswith("+++ b/")})
    with tempfile.TemporaryDirectory(prefix="ghost-patch-", dir=CACHE) as temporary:
        expected = Path(temporary)
        for relative in patched_paths:
            (expected / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(pristine / relative, expected / relative)
        for patch in patches:
            run("patch", "--batch", "-p1", "-i", patch, cwd=expected, stdout=subprocess.DEVNULL)
        generated = {relative: (expected / relative).read_bytes() for relative in patched_paths}
    for path in (ROOT / "native/browser").glob("GHOST_*"):
        generated["intern/ghost/intern/" + path.name] = path.read_bytes()
    for path in (ROOT / "native/browser/webgpu").glob("*"):
        if path.suffix in {".cc", ".hh"}:
            generated["source/blender/gpu/webgpu/" + path.name] = path.read_bytes()
    expression_header = ROOT / "native/browser/expr_math_errors.hh"
    if expression_header.exists():
        generated["source/blender/blenlib/expr_math_errors.hh"] = expression_header.read_bytes()
    startup_relative = "release/datafiles/startup.blend"
    pointer = subprocess.check_output(["git", "-C", str(pristine), "show", "HEAD:" + startup_relative], text=True)
    asset_oid = re.search(r"oid sha256:([a-f0-9]+)", pointer).group(1)
    assets = {startup_relative: asset_oid}
    for path in (pristine / "release/datafiles").rglob("*"):
        if path.is_file():
            with path.open("rb") as stream:
                pointer_data = stream.read(200)
            if pointer_data.startswith(b"version https://git-lfs.github.com/spec/v1\n"):
                oid = re.search(rb"oid sha256:([a-f0-9]{64})", pointer_data).group(1).decode()
                assets[path.relative_to(pristine).as_posix()] = oid
    # Check all copied inputs. Only generated files and the verified LFS asset may differ.
    for origin in pristine.rglob("*"):
        relative = origin.relative_to(pristine).as_posix()
        if ".git" in origin.relative_to(pristine).parts or not origin.is_file() or relative in generated:
            continue
        actual = source / relative
        if not actual.is_file():
            raise SystemExit(f"Prepared source file is missing: {relative}")
        actual_hash = digest(actual)
        if actual_hash != digest(origin) and actual_hash != assets.get(relative):
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
        if not actual.exists() or actual.read_bytes() != data:
            temporary = actual.with_name(actual.name + ".port-" + str(os.getpid()))
            temporary.write_bytes(data)
            temporary.replace(actual)
    missing_assets = [name for name, oid in assets.items() if digest(source / name) != oid]
    if materialize_assets and missing_assets:
        # Blender's public LFS objects are hosted upstream, not in the GitHub mirror.
        endpoint = "https://projects.blender.org/blender/blender.git/info/lfs"
        run("git", "-C", pristine, "-c", "lfs.url=" + endpoint, "-c", "lfs." + endpoint + ".access=none",
            "lfs", "fetch", "--include=release/datafiles/**", "origin", "HEAD",
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
        for name in missing_assets:
            oid = assets[name]
            object_path = pristine / ".git/lfs/objects" / oid[:2] / oid[2:4] / oid
            if not object_path.exists() or digest(object_path) != oid:
                raise SystemExit(f"LFS object could not be verified against Blender's SHA256: {name}")
            shutil.copyfile(object_path, source / name)
    metadata = json.dumps({"commit": head, "patches": {patch.name: digest(patch) for patch in patches},
        "generated": {name: hashlib.sha256(data).hexdigest() for name, data in generated.items()},
        "assets": assets,
        "startup_verified": digest(source / startup_relative) == asset_oid}, indent=2) + "\n"
    temporary = metadata_path.with_name(metadata_path.name + "." + str(os.getpid()))
    temporary.write_text(metadata)
    temporary.replace(metadata_path)
    return source

if __name__ == "__main__":
    toolchain()
    source = prepare_source(materialize_assets="--assets" in sys.argv)
    print("Prepared stable browser source:", source)
