#!/usr/bin/env python3
"""Run the pinned editor link passes with a fresh allocator between passes.

Only the project's O2/Asyncify, non-GC, non-DWARF profile is accepted. Other
invocations (including version checks and small probes) use the original tool.
No validation, runtime assertions or suspension paths are disabled.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time


def configure(env, root, cache, sdk):
    directory = cache / 'binaryen-staged'
    original = Path(env.get('EM_BINARYEN_ROOT', str(sdk / 'upstream')))
    if original.resolve() == directory.resolve():
        original = Path(env['BLENDER_REAL_WASM_OPT']).parent.parent
    binary = original / 'bin/wasm-opt'
    if not binary.is_file():
        raise SystemExit('Missing original Binaryen optimizer: ' + str(binary))
    (directory / 'bin').mkdir(parents=True, exist_ok=True)
    for tool in (original / 'bin').iterdir():
        if not tool.is_file():
            continue
        target = root / 'scripts/low_memory_wasm_opt.py' if tool.name == 'wasm-opt' else tool
        link = directory / 'bin' / tool.name
        if link.is_symlink() and link.resolve() == target.resolve():
            continue
        if link.exists() or link.is_symlink():
            raise SystemExit('Preserve unrecognized staged tool: ' + str(link))
        link.symlink_to(target)
    env['EM_BINARYEN_ROOT'] = str(directory)
    env['BLENDER_REAL_WASM_OPT'] = str(binary)
    env['BLENDER_BINARYEN_STAGE_LOG'] = str(directory / 'progress.jsonl')
    env['BLENDER_BINARYEN_PREFIX_CACHE'] = str(directory / 'prefix-cache')


def digest(path):
    checksum = hashlib.sha256()
    with Path(path).open('rb') as source:
        while block := source.read(1024 * 1024):
            checksum.update(block)
    return checksum.hexdigest()


def prefix_entry(binary, source, controls, names):
    directory = os.environ.get('BLENDER_BINARYEN_PREFIX_CACHE')
    if not directory:
        return None
    configuration = {'input': digest(source), 'tool': digest(binary), 'passes': names,
        'controls': [flag for flag in controls if not flag.startswith('--pass-arg=asyncify-')]}
    key = hashlib.sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest()
    return Path(directory) / key, configuration


def save_prefix(entry, module):
    if not entry:
        return
    directory, configuration = entry
    directory.mkdir(parents=True, exist_ok=True)
    temporary = directory / 'prefix.wasm.tmp'
    shutil.copyfile(module, temporary)
    temporary.replace(directory / 'prefix.wasm')
    (directory / 'prefix.json').write_text(json.dumps({**configuration,
        'output': digest(directory / 'prefix.wasm')}, sort_keys=True) + '\n')


def load_prefix(entry):
    if not entry:
        return None
    directory, configuration = entry
    module, metadata = directory / 'prefix.wasm', directory / 'prefix.json'
    if not module.exists() or not metadata.exists():
        return None
    stored = json.loads(metadata.read_text())
    if configuration != {key: stored.get(key) for key in configuration} or digest(module) != stored.get('output'):
        raise SystemExit('Cached optimizer prefix changed; preserve or remove it: ' + str(directory))
    return module


def record(name, **fields):
    path = os.environ.get('BLENDER_BINARYEN_STAGE_LOG')
    if path:
        with open(path, 'a') as log:
            log.write(json.dumps({'time': time.time(), 'pass': name, **fields}) + '\n')


def split_arguments(args):
    controls, passes = [], []
    source = output = None
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == '-o':
            index += 1
            output = Path(args[index])
        elif arg in ('--strip-target-features', '--post-emscripten', '-O2', '--asyncify'):
            passes.append(arg)
        elif arg in ('-g', '--debuginfo', '--mvp-features', '--low-memory-unused',
                     '--zero-filled-memory') or arg.startswith((
                         '--pass-arg=', '--enable-', '--disable-',
                         '--one-caller-inline-max-function-size=')):
            controls.append(arg)
        elif not arg.startswith('-') and source is None:
            source = Path(arg)
        else:
            raise SystemExit('Unsupported staged optimizer argument: ' + arg)
        index += 1
    if source is None or output is None or passes != [
            '--strip-target-features', '--post-emscripten', '-O2', '--asyncify']:
        raise SystemExit('Staged optimizer requires the pinned O2/Asyncify pass order.')
    if '--mvp-features' not in controls or any(flag in controls for flag in (
            '--enable-gc', '--enable-strings', '--enable-memory64')):
        raise SystemExit('Unsupported staged optimizer feature profile.')
    return source, output, controls


def reject_dwarf(path):
    """The O2 pass list depends on DWARF; this build deliberately uses -g2."""
    def leb(stream):
        value = shift = 0
        while True:
            byte = stream.read(1)
            if not byte or shift > 35:
                raise SystemExit('Invalid WebAssembly section header.')
            value |= (byte[0] & 127) << shift
            if byte[0] < 128:
                return value
            shift += 7
    with path.open('rb') as module:
        if module.read(8) != b'\0asm\x01\0\0\0':
            return  # Text modules are used only by the wrapper regression.
        while section := module.read(1):
            size = leb(module)
            end = module.tell() + size
            if section == b'\0':
                name = module.read(leb(module))
                if name.startswith(b'.debug_'):
                    raise SystemExit('Staged linking does not support DWARF; use -g2.')
            module.seek(end)


def stage_link(binary, args):
    source, output, controls = split_arguments(args)
    reject_dwarf(source)
    # These feature/control flags produce the same non-GC O2 pipeline on a tiny
    # module. Pass-debug level 1 prints top-level passes from the actual pinned
    # tool; nested passes stay inside their owning pass and are not duplicated.
    with tempfile.TemporaryDirectory(prefix='binaryen-stages-', dir=output.parent) as temp:
        temp = Path(temp)
        probe = temp / 'probe.wat'
        probe.write_text('(module (memory 1) (func (export "probe") (param i32) '
                         '(result i32) (i32.add (local.get 0) (i32.const 7))))')
        debug_env = {**os.environ, 'BINARYEN_PASS_DEBUG': '1'}
        query = subprocess.run([str(binary), *controls, '--strip-target-features',
            '--post-emscripten', '-O2', str(probe), '-o', str(temp / 'probe.wasm')],
            env=debug_env, text=True, capture_output=True, check=True)
        names = re.findall(r'\[PassRunner\]\s+running pass: ([\w-]+)\.\.\.', query.stderr)
        if not names or names[:2] != ['strip-target-features', 'post-emscripten']:
            raise SystemExit('Cannot determine the pinned optimizer pass sequence: ' + query.stderr)
        names.append('asyncify')
        entry = prefix_entry(binary, source, controls, names[:-1])
        cached = load_prefix(entry)
        if cached:
            record('prefix-cache-hit', module=str(cached))
        record('start', source=str(source), stages=names,
               version=subprocess.check_output([str(binary), '--version'], text=True).strip())
        environment = dict(os.environ)
        environment.pop('BINARYEN_PASS_DEBUG', None)
        current = cached or source
        for index, name in enumerate(names):
            if cached and name != 'asyncify':
                continue
            destination = temp / ('stage-' + str(index % 2) + '.wasm')
            record(name, index=index, total=len(names), state='running')
            subprocess.run([str(binary), *controls, '--optimize-level=2', '--shrink-level=0',
                '--' + name, str(current), '-o', str(destination)], env=environment, check=True)
            current = destination
            record(name, index=index, state='done', bytes=current.stat().st_size)
            if index == len(names) - 2:
                save_prefix(entry, current)
        current.replace(output)
        record('complete', output=str(output), bytes=output.stat().st_size)


def main():
    binary = Path(os.environ['BLENDER_REAL_WASM_OPT'])
    args = sys.argv[1:]
    if '-O2' not in args or '--asyncify' not in args:
        return subprocess.run([str(binary), *args]).returncode
    source, _, _ = split_arguments(args)
    if source.stat().st_size < 64 * 1024 * 1024:
        return subprocess.run([str(binary), *args]).returncode
    stage_link(binary, args)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
