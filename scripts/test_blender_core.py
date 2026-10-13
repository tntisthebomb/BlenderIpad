#!/usr/bin/env python3
"""Test bpy and .blend I/O in the real compiled application; no substitutes."""
import argparse
import hashlib
import json
from setup_browser import CACHE, ROOT, toolchain, run

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument('--webgpu',action='store_true')
    args=parser.parse_args()
    env = toolchain()
    profile='blender-webgpu' if args.webgpu else 'blender-core'
    binary = CACHE / (profile+"-build/bin/blender.js")
    if not binary.exists():
        raise SystemExit("The full background application has not linked yet.")
    output = CACHE / (profile+"-scene-test")
    output.mkdir(exist_ok=True)
    result = output / "result.json"
    stamp = CACHE / (profile+"-build/core-validation.json")
    if stamp.exists():
        stamp.unlink()
    if result.exists():
        result.unlink()
    source = CACHE / "blender-browser"
    user_cache = CACHE / (profile+"-user-cache")
    user_cache.mkdir(exist_ok=True)
    env.update({"BLENDER_SYSTEM_RESOURCES": str(source),
                "BLENDER_SYSTEM_SCRIPTS": str(source / "scripts"),
                "BLENDER_SYSTEM_DATAFILES": str(source / "release/datafiles"),
                "BLENDER_SYSTEM_PYTHON": str(CACHE / "wasm-threaded-sysroot"),
                "PYTHONHOME": str(CACHE / "wasm-threaded-sysroot"),
                "XDG_CACHE_HOME": str(user_cache)})
    run(CACHE / "emsdk/node/22.16.0_64bit/bin/node", binary,
        "--background", "--factory-startup", "--disable-autoexec", "--threads", "2",
        "--python-exit-code", "1", "--python", ROOT / "tests/blender_core_scene.py",
        "--", output, source / "release/datafiles/startup.blend", env=env)
    if not result.exists():
        raise SystemExit("The application did not complete the scene test.")
    checks = json.loads(result.read_text())
    if checks["version"] != [5, 2, 2] or not all(value is True for key, value in checks.items() if key != "version"):
        raise SystemExit("Incomplete core workflow validation")
    stamp.write_text(json.dumps({"checks": checks,
        "scene_test_sha256": hashlib.sha256((ROOT / "tests/blender_core_scene.py").read_bytes()).hexdigest(),
        "files": {
        name: hashlib.sha256((binary.parent / name).read_bytes()).hexdigest()
        for name in ("blender.js", "blender.wasm")}}, indent=2) + "\n")
    print("PASS: actual Blender bpy, original startup fixture, modeling, solidify, animation, PNG image I/O and native .blend roundtrip.")
