#!/usr/bin/env python3
"""Compare actual repeated suspension under combined and staged Binaryen."""
import subprocess
from setup_browser import CACHE, ROOT, toolchain, run


if __name__ == '__main__':
    env = toolchain()
    output = CACHE / 'binaryen-probe'
    output.mkdir(exist_ok=True)
    (output / 'package.json').write_text('{"type":"commonjs"}\n')
    node = CACHE / 'emsdk/node/22.16.0_64bit/bin/node'
    results = []
    for variant in ('combined', 'staged'):
        current = dict(env)
        if variant == 'combined':
            current.pop('EM_BINARYEN_ROOT')
        binary = output / (variant + '.js')
        run('emcc', ROOT / 'tests/binaryen_suspend_probe.c', '-O2',
            '-sASYNCIFY=1', '-sASSERTIONS=2', '-sENVIRONMENT=node',
            '-o', binary, env=current)
        result = subprocess.check_output([str(node), str(binary)], env=current, text=True)
        if result.strip() != 'PASS: resumed exact state 21':
            raise SystemExit('Suspension/state acceptance failed: ' + result)
        results.append(result)
    if results[0] != results[1]:
        raise SystemExit('Combined and staged optimizer outputs differ.')
    print('PASS: staged Binaryen preserves repeated suspension and state assertions.')
