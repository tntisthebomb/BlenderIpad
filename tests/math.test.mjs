// SPDX-License-Identifier: GPL-2.0-or-later
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { loadMath, checkMath, result } from '../web/math-runtime.js';

const bytes = await fs.readFile(new URL('../web/engine/blender-math.wasm', import.meta.url));
const engine = await loadMath(bytes);
const close = (a, b, tolerance = 2e-4) => {
  a.forEach((x, i) => assert.ok(Math.abs(x - b[i]) < tolerance, `${a} differs from ${b}`));
};
test('pinned Blender source version and five representative math checks', () => {
  assert.equal(engine.bp_version(), 50202);
  assert.equal(checkMath(engine), 5);
});
test('256 deterministic transforms invert to their original points', () => {
  for (let i = 0; i < 256; i++) {
    const point = [Math.sin(i), Math.cos(i * 3), Math.sin(i * 0.7) * 3];
    const location = [i / 25 - 5, Math.cos(i) * 2, Math.sin(i / 11)];
    const rotation = [i * 0.13, i * 0.27, i * 0.19];
    const scale = [0.3 + i % 7, -(0.4 + i % 3), 0.5 + i % 11];
    engine.bp_transform(...point, ...location, ...rotation, ...scale);
    assert.equal(engine.bp_untransform(...result(engine)), 1);
    close(result(engine), point);
  }
});
test('singular scale fails inversion instead of reporting success', () => {
  engine.bp_transform(1, 2, 3, 0, 0, 0, 0, 0, 0, 0, 1, 1);
  assert.equal(engine.bp_untransform(...result(engine)), 0);
});
test('interpolation endpoints and extrapolation use upstream Blender code', () => {
  for (const t of [-1, 0, 0.3, 1, 2]) {
    engine.bp_interpolate(1, 2, 3, 4, 6, 9, t);
    close(result(engine), [1 + 3 * t, 2 + 4 * t, 3 + 6 * t]);
  }
});
test('zero vector normalization is defined', () => {
  assert.equal(engine.bp_normalize(0, 0, 0), 0);
  close(result(engine), [0, 0, 0]);
});
test('Blender assertions remain active and abort the reactor', async () => {
  const diagnostics = [];
  const fresh = await loadMath(bytes, line => diagnostics.push(line));
  assert.throws(() => fresh.bp_assert_for_test(), WebAssembly.RuntimeError);
  assert.ok(diagnostics.join('').includes('BLI_assert failed'));
});
test('ABI rejects out-of-range result indices through Blender assertion', async () => {
  const fresh = await loadMath(bytes, () => {});
  assert.throws(() => fresh.bp_result_at(3), WebAssembly.RuntimeError);
});
