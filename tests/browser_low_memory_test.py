#!/usr/bin/env python3
"""Verify the packaging transformation preserves executable bytes and rejects drift."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from browser_low_memory import HEADER,strip_debug_names
# Real valid empty-module standard sections, plus an unused custom name section.
original=HEADER+b'\x00\x05\x04name'+b'\x01\x01\x00'
stripped,proof=strip_debug_names(original)
assert stripped==HEADER+b'\x01\x01\x00'
assert proof['removedBytes']==7
for invalid in (HEADER,original[:-1],original+b'\x00\x05\x04name',HEADER+b'\x01\xff\xff\xff\xff\x10'):
    try:strip_debug_names(invalid)
    except ValueError:pass
    else:raise AssertionError('Accepted malformed or unrecognized WASM')
print('PASS: name-only removal preserves retained sections; malformed/truncated/drifted inputs rejected.')
