#!/usr/bin/env python3
"""Link the real static CPython archive into a browser C-API integration test."""
import shutil
import zipfile
from setup_browser import CACHE, ROOT, toolchain, run

if __name__ == "__main__":
    env = toolchain()
    prefix = CACHE / "wasm-threaded-sysroot"
    if not (prefix / "python-runtime.json").exists():
        raise SystemExit("Build and validate the matching Python runtime first.")
    build = CACHE / "python-browser"
    build.mkdir(exist_ok=True)
    stdlib = prefix / "lib/python3.13"
    archive = build / "python313.zip"
    excluded = {"test", "tests", "idlelib", "ensurepip", "tkinter", "turtledemo", "__pycache__"}
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for path in sorted(stdlib.rglob("*")):
            relative = path.relative_to(stdlib)
            if not path.is_file() or any(x in excluded or x.startswith("config-") for x in relative.parts):
                continue
            if path.suffix != ".py":
                continue
            info = zipfile.ZipInfo(relative.as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            output.writestr(info, path.read_bytes())
    run("emcc", ROOT / "native/browser/python_runtime_probe.c",
        "-I" + str(prefix / "include/python3.13"), prefix / "lib/libpython3.13.a",
        "-O1", "-g", "-pthread", "-fexceptions", "-DPY_CALL_TRAMPOLINE",
        "-sUSE_ZLIB=1", "-sUSE_BZIP2=1", "--no-entry", "-sMODULARIZE=1",
        "-sEXPORT_NAME=createBlenderPython", "-sENVIRONMENT=web,worker",
        "-sALLOW_MEMORY_GROWTH=1", "-sINITIAL_MEMORY=67108864", "-sMAXIMUM_MEMORY=536870912",
        "-sSTACK_SIZE=4194304", "-sDEFAULT_PTHREAD_STACK_SIZE=2097152", "-sPTHREAD_POOL_SIZE=2",
        "-sPTHREAD_POOL_SIZE_STRICT=0", "-sASSERTIONS=2", "-sDISABLE_EXCEPTION_CATCHING=0", "-sASYNCIFY=0",
        "-sEXPORTED_FUNCTIONS=['_python_runtime_initialize','_python_runtime_execute','_python_runtime_error','_python_runtime_finalize']",
        "-sEXPORTED_RUNTIME_METHODS=['ccall','UTF8ToString']",
        "--preload-file", str(archive) + "@/python/lib/python313.zip",
        "-o", build / "python-runtime.js", env=env)
    shutil.copyfile(ROOT / "native/browser/python_runtime.html", build / "runtime.html")
    shutil.copyfile(CACHE / "deps-src/Python-3.13.13/LICENSE", build / "PYTHON-LICENSE.txt")
    print("Linked actual CPython C API and zipped standard library; this probe does not test bpy or the editor.")
