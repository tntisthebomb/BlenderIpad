#!/usr/bin/env python3
"""Compile the Blender math milestone, not a complete Blender executable."""
import hashlib
import json
from pathlib import Path
import subprocess
import io
import tarfile
from setup import ROOT, CACHE, LOCK, setup

def build():
    setup()
    compiler = CACHE / "wasi-sdk-25.0-x86_64-linux" / "bin" / "clang++"
    source = CACHE / "blender"
    bli = source / "source/blender/blenlib"
    out = ROOT / "web/engine"
    out.mkdir(parents=True, exist_ok=True)
    output = out / "blender-math.wasm"
    units = [bli / "intern" / name for name in
             ("math_matrix_c.cc", "math_rotation_c.cc", "math_vector.cc", "math_base.cc", "BLI_assert.cc")]
    exports = ("bp_version", "bp_result_at", "bp_transform", "bp_untransform", "bp_interpolate",
               "bp_normalize", "bp_assert_for_test")
    subprocess.run([
        str(compiler), "-std=c++20", "-O2", "-mexec-model=reactor", "-DMATH_STANDALONE", "-DWITH_ASSERT_ABORT",
        "-fno-exceptions", "-fno-rtti", "-ffunction-sections", "-fdata-sections",
        "-I" + str(bli), "-I" + str(source / "source/blender/blenkernel"),
        "-I" + str(source / "source/blender/makesdna"),
        str(ROOT / "native/kernel.cc"), *map(str, units), "-Wl,--no-entry", "-Wl,--gc-sections",
        "-Wl,--export-memory", "-Wl,--initial-memory=2097152", "-Wl,--max-memory=16777216",
        *["-Wl,--export=" + name for name in exports], "-o", str(output)
    ], check=True)
    inputs = [ROOT / "native/kernel.cc", *units]
    manifest = {
        "blender": LOCK["blender"], "scope": "blenlib math only; no Blender UI or rendering",
        "compiler": "wasi-sdk " + LOCK["wasi_sdk"]["version"],
        "wasm_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "inputs": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    }
    (out / "build.json").write_text(json.dumps(manifest, indent=2) + "\n")
    # Ship corresponding source and a standalone rebuild script alongside the binary.
    # The entire blenlib and DNA directories preserve included headers and notices.
    rebuild = '''#!/usr/bin/env python3
import os, pathlib, subprocess
r = pathlib.Path(__file__).resolve().parent
s = r / "upstream/source/blender"
c = pathlib.Path(os.environ["WASI_SDK_PATH"]) / "bin/clang++"
units = [s / "blenlib/intern" / n for n in
         ("math_matrix_c.cc", "math_rotation_c.cc", "math_vector.cc", "math_base.cc", "BLI_assert.cc")]
exports = ("bp_version", "bp_result_at", "bp_transform", "bp_untransform", "bp_interpolate",
           "bp_normalize", "bp_assert_for_test")
subprocess.run([str(c), "-std=c++20", "-O2", "-mexec-model=reactor", "-DMATH_STANDALONE",
    "-DWITH_ASSERT_ABORT", "-fno-exceptions", "-fno-rtti", "-ffunction-sections", "-fdata-sections",
    *["-I" + str(s / p) for p in ("blenlib", "blenkernel", "makesdna")],
    str(r / "native/kernel.cc"), *map(str, units), "-Wl,--no-entry", "-Wl,--gc-sections",
    "-Wl,--export-memory", "-Wl,--initial-memory=2097152", "-Wl,--max-memory=16777216",
    *["-Wl,--export=" + p for p in exports], "-o", str(r / "blender-math.wasm")], check=True)
'''
    with tarfile.open(out / "source.tar.gz", "w:gz") as bundle:
        for path in ("source/blender/blenlib", "source/blender/makesdna",
                     "source/blender/blenkernel/BKE_blender_version.h", "doc/license/GPL-license.txt", "COPYING"):
            bundle.add(source / path, arcname="upstream/" + path)
        bundle.add(ROOT / "native/kernel.cc", arcname="native/kernel.cc")
        bundle.add(ROOT / "port.lock.json", arcname="port.lock.json")
        payload = rebuild.encode()
        info = tarfile.TarInfo("rebuild.py"); info.size = len(payload); info.mode = 0o755
        bundle.addfile(info, io.BytesIO(payload))
    print(f"Built {output} ({output.stat().st_size} bytes).")

if __name__ == "__main__":
    build()
