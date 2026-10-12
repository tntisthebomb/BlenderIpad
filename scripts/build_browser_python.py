#!/usr/bin/env python3
"""Build Blender's pinned CPython as a real embeddable Emscripten runtime."""
import json
import shutil
from setup_browser import CACHE, LOCK, toolchain, run
from build_browser_deps import fetch

if __name__ == "__main__":
    env = toolchain()
    source = fetch("python")
    prefix = CACHE / "wasm-threaded-sysroot"
    host = CACHE / "deps-build/python-host"
    wasm = CACHE / "deps-build/python-wasm"
    host.mkdir(parents=True, exist_ok=True)
    wasm.mkdir(parents=True, exist_ok=True)
    (wasm / "package.json").write_text('{"type":"commonjs"}\n')
    if not (host / "Makefile").exists():
        run(source / "configure", "--without-ensurepip", cwd=host)
    run("make", "-j4", cwd=host)
    build_python = host / "python"
    run(build_python, "-c", "import binascii, zlib; import sys; assert sys.version_info[:3] == (3,13,13)")
    if not (prefix / "lib/libz.a").exists():
        raise SystemExit("Build the matching pthread zlib first: python3 scripts/build_browser_deps.py --threaded zlib")
    cross_env = {**env,
        "CONFIG_SITE": str(source / "Tools/wasm/config.site-wasm32-emscripten"),
        "CFLAGS": "-O2 -pthread -fexceptions -DPY_CALL_TRAMPOLINE",
        "CPPFLAGS": "-I" + str(prefix / "include"),
        "LDFLAGS": "-L" + str(prefix / "lib") + " -sASSERTIONS=2 -sDISABLE_EXCEPTION_CATCHING=0 -sSTACK_SIZE=4194304 -sDEFAULT_PTHREAD_STACK_SIZE=2097152",
        "PKG_CONFIG_LIBDIR": str(prefix / "lib/pkgconfig"),
        "PKG_CONFIG_PATH": "",
    }
    run("emconfigure", source / "configure", "--host=wasm32-unknown-emscripten",
        "--build=x86_64-pc-linux-gnu", "--with-emscripten-target=node",
        "--enable-wasm-pthreads", "--with-build-python=" + str(build_python),
        "--prefix=" + str(prefix), "--disable-shared", "--disable-test-modules",
        "--with-ensurepip=no", cwd=wasm, env=cross_env)
    # Relink CLI targets after configuration flag changes even when no C input
    # changed. Make's supported -W override preserves all source/object files.
    run("emmake", "make", "-j4", "-W", "libpython3.13.a", cwd=wasm, env=cross_env)
    run("emmake", "make", "install", cwd=wasm, env=cross_env)
    node = CACHE / "emsdk/node/22.16.0_64bit/bin/node"
    # Exercise the actual interpreter before making it available for embedding.
    run(node, wasm / "python.js", "-c",
        "import sys,json,math,decimal,_decimal,zlib,hashlib,xml.etree.ElementTree as E; "
        "assert sys.version_info[:3] == (3,13,13); "
        "assert json.loads(json.dumps({'text':'iPad é'}))['text']=='iPad é'; "
        "assert math.isclose(math.sqrt(81),9); "
        "assert str(decimal.Decimal('0.1')+decimal.Decimal('0.2'))=='0.3'; "
        "assert zlib.decompress(zlib.compress(b'Blender'*1024))==b'Blender'*1024; "
        "assert hashlib.sha256(b'abc').hexdigest()=='ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'; "
        "assert E.fromstring('<scene><mesh/></scene>')[0].tag=='mesh'; "
        "print('PASS: pinned CPython WASM, UTF-8/JSON, math, decimal, compression, hashing and XML')",
        cwd=wasm, env=env)
    # Preserve support objects omitted from CPython's embeddable archive. Use
    # distinct member names to avoid replacing core context.o or io.o members.
    archive = prefix / "lib/libpython3.13.a"
    extras = sorted((wasm / "Modules/_decimal/libmpdec").glob("*.o"))
    extras += [wasm / "Modules" / x for x in ["expat/xmlparse.o", "expat/xmltok.o", "expat/xmlrole.o", "_hacl/Hacl_Hash_SHA2.o"]]
    staged = wasm / "embed-support"
    staged.mkdir(exist_ok=True)
    # CPython namespaces Expat's public API, but these newer internal globals
    # are absent from pyexpatns.h. Keep its bundled Expat independent of OCIO's
    # Expat, including references between all three translation units.
    run("emmake", "make", "-j4", "-W", source / "Modules/expat/expat_config.h",
        "EXTRA_CFLAGS=-Dg_reparseDeferralEnabledDefault=PyExpat_reparseDeferralEnabledDefault "
        "-D_INTERNAL_trim_to_complete_utf8_characters=PyExpat_trim_to_complete_utf8_characters",
        "Modules/expat/xmlparse.o", "Modules/expat/xmltok.o", "Modules/expat/xmlrole.o",
        cwd=wasm, env=cross_env)
    for obj in extras:
        if obj.is_file():
            target = staged / ("pymod_" + obj.relative_to(wasm / "Modules").as_posix().replace("/", "_"))
            shutil.copyfile(obj, target)
            run("emar", "r", archive, target, env=env)
    (prefix / "python-runtime.json").write_text(json.dumps({
        "version": "3.13.13", "emscripten": LOCK["emsdk"]["version"],
        "pthread": True, "scope": "Embeddable CPython; standalone validation does not establish bpy or editor integration"
    }, indent=2) + "\n")
