# Tint atomic composite lowering backport

`tint-atomics-composite.patch` adapts three upstream Dawn fixes to the SDK-matched
Dawn commit `01940842b667a7812d0e4ca0ef4367fbec294241`:

- [ea8960edcec573edb69ba941a7c59c3dacad019c](https://github.com/google/dawn/commit/ea8960edcec573edb69ba941a7c59c3dacad019c): propagate atomic types through access results.
- [97e9dc83e5022a7c7b15d6895ae9cc09808c2d2d](https://github.com/google/dawn/commit/97e9dc83e5022a7c7b15d6895ae9cc09808c2d2d): decompose whole structure/array loads and stores containing atomics.
- [a1d982581441147e539502b19d65a9ad570d43a9](https://github.com/google/dawn/commit/a1d982581441147e539502b19d65a9ad570d43a9): propagate member types through vector/matrix indexing.

The backport retains the pinned version's `TINT_ASSERT` and IR validation APIs.
It does not catch compiler assertions or suppress validation. The implementation
retains Dawn's BSD-3-Clause license header. The build applies this patch to a
separate guarded source file and substitutes that single compilation unit through
CMake; the pinned Dawn Git checkout remains clean. Unknown edits to the generated
file cause the build to stop.

Blender's `draw_command_generate` shader loads `DrawGroup` from storage while
atomically updating its counters. The pinned translator previously asserted when
converting this whole structure load. The captured shader is a development
reproducer; `tests/shader_atomic_composite.comp` provides a small durable
regression covering mixed atomic/non-atomic structure, vector and array values.
`tests/shader_atomic_webgpu_test.py` checks exact GPU readback after translation.
