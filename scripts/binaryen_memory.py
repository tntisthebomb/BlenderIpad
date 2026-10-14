#!/usr/bin/env python3
"""Run the pinned Binaryen passes with an independent Asyncify process.

The full Blender IR plus optimizer temporaries and suspension rewriting exceeds
8 GiB when held in one process. Preserve the pass order and tuning options, but
serialize the optimized IR between optimization and instrumentation.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def split(arguments, intermediate):
    boundary = arguments.index('--asyncify')
    output_flag = arguments.index('-o')
    source, destination = arguments[output_flag - 1:output_flag + 2:2]
    # Emscripten puts the input immediately before -o. Only handle this known
    # invocation; source maps need separate metadata updates in both stages.
    if not source.endswith('.wasm') or any('source-map' in a for a in arguments):
        raise ValueError('Unsupported Asyncify invocation for memory staging')
    prefix = arguments[:boundary]
    suffix = arguments[boundary:output_flag - 1] + arguments[output_flag + 2:]
    common, instrumentation = [], []
    for option in suffix:
        if option == '--asyncify' or option.startswith('--pass-arg=asyncify-') or option == '--zero-filled-memory':
            instrumentation.append(option)
        elif (option == '-g' or option == '--mvp-features' or option.startswith('--enable-')
              or option.startswith('--disable-') or option.startswith('--pass-arg=')
              or option.startswith('--one-caller-inline-max-function-size=')):
            common.append(option)
        else:
            raise ValueError('Unrecognized post-Asyncify option: ' + option)
    return (prefix + common + [source, '-o', intermediate],
            instrumentation + common + [intermediate, '-o', destination])


def main():
    real = os.environ['BLENDER_BINARYEN_WASM_OPT']
    arguments = sys.argv[1:]
    if '--asyncify' not in arguments:
        return subprocess.call([real, *arguments])
    with tempfile.TemporaryDirectory(prefix='blender-binaryen-') as temporary:
        first, second = split(arguments, str(Path(temporary) / 'optimized.wasm'))
        print('Binaryen: optimizing before separate Asyncify instrumentation', file=sys.stderr, flush=True)
        result = subprocess.call([real, *first])
        if result:
            return result
        print('Binaryen: instrumenting optimized module with Asyncify', file=sys.stderr, flush=True)
        return subprocess.call([real, *second])


if __name__ == '__main__':
    sys.exit(main())
