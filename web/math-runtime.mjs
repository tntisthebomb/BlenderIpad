// SPDX-License-Identifier: GPL-2.0-or-later
// Minimal WASI host for this math reactor. Unsupported OS calls fail explicitly.
export async function loadMath(bytes, log = console.error) {
  let instance;
  const memory = () => new DataView(instance.exports.memory.buffer);
  const wasi = {
    fd_close: () => 8, // EBADF: this reactor owns no filesystem descriptors.
    fd_seek: () => 70, // ESPIPE: stdout/stderr are streams.
    fd_fdstat_get(fd, pointer) {
      if (fd !== 1 && fd !== 2) return 8;
      const view = memory();
      for (let i = 0; i < 24; i++) view.setUint8(pointer + i, 0);
      view.setUint8(pointer, 2); // character device
      view.setBigUint64(pointer + 8, 64n, true); // FD_WRITE
      return 0;
    },
    fd_write(fd, vectors, count, written) {
      if (fd !== 1 && fd !== 2) return 8;
      const view = memory();
      let total = 0;
      for (let i = 0; i < count; i++) {
        const pointer = view.getUint32(vectors + i * 8, true);
        const size = view.getUint32(vectors + i * 8 + 4, true);
        log(new TextDecoder().decode(new Uint8Array(instance.exports.memory.buffer, pointer, size)));
        total += size;
      }
      view.setUint32(written, total, true);
      return 0;
    },
    proc_exit(code) { throw new Error(`Blender math reactor exited with code ${code}`); },
  };
  const module = await WebAssembly.compile(bytes);
  for (const item of WebAssembly.Module.imports(module)) {
    if (item.module !== 'wasi_snapshot_preview1' || !(item.name in wasi)) {
      throw new Error(`Unsupported reactor import: ${item.module}.${item.name}`);
    }
  }
  instance = await WebAssembly.instantiate(module, { wasi_snapshot_preview1: wasi });
  instance.exports._initialize?.();
  if (instance.exports.bp_version() !== 50202) throw new Error('Unexpected Blender source version');
  return instance.exports;
}

export function result(engine) {
  return [0, 1, 2].map(axis => engine.bp_result_at(axis));
}

export function checkMath(engine) {
  const close = (actual, expected) => {
    if (actual.length !== expected.length || actual.some((x, i) => Math.abs(x - expected[i]) > 1e-5)) {
      throw new Error(`Blender math mismatch: ${actual} / ${expected}`);
    }
  };
  engine.bp_transform(1, 2, 3, 4, 5, 6, 0, 0, 0, 2, 3, 4);
  close(result(engine), [6, 11, 18]);
  if (!engine.bp_untransform(6, 11, 18)) throw new Error('Matrix inversion failed');
  close(result(engine), [1, 2, 3]);
  engine.bp_transform(1, 0, 0, 0, 0, 0, 0, 0, Math.PI / 2, 1, 1, 1);
  close(result(engine), [0, 1, 0]);
  engine.bp_interpolate(0, 2, 4, 4, 6, 8, 0.25);
  close(result(engine), [1, 3, 5]);
  if (Math.abs(engine.bp_normalize(3, 4, 0) - 5) > 1e-5) throw new Error('Normalization failed');
  close(result(engine), [0.6, 0.8, 0]);
  return 5;
}
