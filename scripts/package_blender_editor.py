#!/usr/bin/env python3
"""Package the accepted experimental editor and its corresponding source."""
import io
import json
import posixpath
from pathlib import Path
import subprocess
import tarfile
import zipfile

from setup_browser import CACHE, ROOT
from validate_blender_editor import ASSETS, snapshot

NAME = 'BlenderIpad-5.2.2-editor-preview'
EXCLUDED = {'.git', '__pycache__', 'node_modules', '.pytest_cache'}
NOTICE = '''Experimental Blender 5.2.2 browser editor

This is an incomplete browser port. The native editor, viewport, keyboard,
touch selection, project save/load and offline reload passed Chromium tests.
Cycles and several optional features are disabled. Safari/iPad acceptance and
render engine validation remain outstanding. Initial shader compilation is slow.

Serve these files from HTTPS with these response headers:
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
Cross-Origin-Resource-Policy: same-origin

WebGPU and cross-origin isolation are required. Plain HTTP .local hosting is
insufficient. An installed offline application computes locally on your device.
Keep backups of exported projects; browsers can evict site storage.

The combined application is distributed under GPL-3.0-or-later. See LICENSE.txt
and THIRD_PARTY.md. Corresponding source accompanies this build separately.
'''


def add_text(archive, name, text):
    data = text.encode()
    entry = tarfile.TarInfo(name)
    entry.size = len(data)
    entry.mode = 0o644
    archive.addfile(entry, io.BytesIO(data))


def source_filter(entry):
    if EXCLUDED.intersection(Path(entry.name).parts):
        return None
    # Do not include links escaping the source bundle, device files or pipes.
    if entry.issym() or entry.islnk():
        target = Path(entry.linkname)
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(entry.name), entry.linkname))
        if target.is_absolute() or resolved == '..' or resolved.startswith('../'):
            raise SystemExit('Unsafe source archive link: ' + entry.name)
    elif not (entry.isfile() or entry.isdir()):
        raise SystemExit('Unsupported source archive entry: ' + entry.name)
    return entry


def main():
    directory = CACHE / 'blender-webgpu-browser'
    proof = json.loads((directory / 'editor-validation.json').read_text())
    if proof.get('profile') != 'experimental-editor' or proof.get('version') != [5, 2, 2]:
        raise SystemExit('Acceptance proof does not match this editor profile.')
    if snapshot() != {key: proof[key] for key in ('assets', 'tests')}:
        raise SystemExit('Assets or fixtures changed after acceptance; revalidate before packaging.')
    source_trees = {
        'blender-prepared': CACHE / 'blender-browser',
        'dependencies': CACHE / 'deps-src',
        'graphics': CACHE / 'graphics-src',
        'overlays/openimageio': CACHE / 'deps-build/openimageio-threaded/port-source',
        'overlays/pystring': CACHE / 'deps-build/pystring-threaded/source',
        'overlays/tint': CACHE / 'tint-patched-source',
        'emscripten/system': CACHE / 'emsdk/upstream/emscripten/system',
        'emscripten/src': CACHE / 'emsdk/upstream/emscripten/src',
    }
    for path in source_trees.values():
        if not path.is_dir():
            raise SystemExit('Missing corresponding source: ' + str(path))
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    source_name = NAME + '-source.tar.gz'
    source_path = output / source_name
    temporary = output / (source_name + '.tmp')
    with tarfile.open(temporary, 'w:gz', compresslevel=6, dereference=False) as archive:
        tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
        # Include these new packaging instructions even before their first commit.
        tracked = sorted(set(filter(None, tracked)) | {
            'scripts/package_blender_editor.py', 'scripts/validate_blender_editor.py'})
        for relative in tracked:
            archive.add(ROOT / relative, arcname='port/' + relative, recursive=False,
                        filter=source_filter)
        for relative, path in source_trees.items():
            archive.add(path, arcname=relative, filter=source_filter)
        add_text(archive, 'REBUILD.txt', '''Corresponding source for the experimental editor\n\nThe port/ tree contains all build scripts, patches, toolchain/dependency pins,\nlicenses and tests. blender-prepared/ is the materialized Blender source used\nfor this build; dependencies/ and graphics/ contain the dependency sources.\nThe overlays/ directory contains the exact patched dependency files.\nemscripten/ includes the embedded system libraries and JavaScript runtime.\n\nBuild on Linux x86-64 following port/BROWSER_PORT.md and port/README.md.\nRun the pinned build scripts from port/. They download verified toolchains and\nrecreate the guarded source overlays; Internet is needed for a fresh build.\nThe application itself runs locally and supports offline operation.\nRun scripts/validate_blender_editor.py before scripts/package_blender_editor.py.\n''')
        add_text(archive, 'editor-validation.json', json.dumps(proof, indent=2) + '\n')
    temporary.replace(source_path)
    app_path = output / (NAME + '.zip')
    temporary_app = output / (NAME + '.zip.tmp')
    with zipfile.ZipFile(temporary_app, 'w', compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6) as archive:
        for name in ASSETS:
            archive.write(directory / name, name)
        archive.writestr('README.txt', NOTICE + '\nCorresponding source: ' + source_name + '\n')
        archive.write(ROOT / 'native/browser/LICENSE-GPL-3.0.txt', 'LICENSE.txt')
        archive.write(ROOT / 'THIRD_PARTY.md', 'THIRD_PARTY.md')
        archive.write(directory / 'editor-validation.json', 'editor-validation.json')
    if snapshot() != {key: proof[key] for key in ('assets', 'tests')}:
        temporary_app.unlink()
        source_path.unlink()
        raise SystemExit('Accepted files changed while packaging.')
    temporary_app.replace(app_path)
    print('Packaged experimental editor:', app_path)
    print('Packaged corresponding source:', source_path)


if __name__ == '__main__':
    main()
