/* SPDX-License-Identifier: GPL-2.0-or-later */
// Browser ABI around unmodified Blender math code. This is not the Blender application.
#include "BLI_math_matrix.h"
#include "BLI_math_vector.h"
#include "BLI_system.h"
#include "BKE_blender_version.h"

static float result[3];
static float transform[4][4];

namespace blender {
// WASI has no native stack unwinder. Assertions still print and abort using BLI_assert.cc.
void BLI_system_backtrace(FILE *) {}
}

extern "C" {
int bp_version() { return BLENDER_VERSION * 100 + BLENDER_VERSION_PATCH; }
float bp_result_at(int axis) {
  BLI_assert(axis >= 0 && axis < 3);
  return result[axis];
}
void bp_transform(float x, float y, float z,
                  float tx, float ty, float tz,
                  float rx, float ry, float rz,
                  float sx, float sy, float sz) {
  const float point[3] = {x, y, z};
  const float location[3] = {tx, ty, tz};
  const float rotation[3] = {rx, ry, rz};
  const float scale[3] = {sx, sy, sz};
  blender::loc_eul_size_to_mat4(transform, location, rotation, scale);
  blender::mul_v3_m4v3(result, transform, point);
}
int bp_untransform(float x, float y, float z) {
  float inverse[4][4];
  if (!blender::invert_m4_m4(inverse, transform)) { return 0; }
  const float point[3] = {x, y, z};
  blender::mul_v3_m4v3(result, inverse, point);
  return 1;
}
void bp_interpolate(float ax, float ay, float az, float bx, float by, float bz, float t) {
  const float a[3] = {ax, ay, az}, b[3] = {bx, by, bz};
  blender::interp_v3_v3v3(result, a, b, t);
}
float bp_normalize(float x, float y, float z) {
  result[0] = x; result[1] = y; result[2] = z;
  return blender::normalize_v3(result);
}
void bp_assert_for_test() { BLI_assert(false); }
}
