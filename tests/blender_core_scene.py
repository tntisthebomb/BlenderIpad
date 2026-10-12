# SPDX-License-Identifier: GPL-2.0-or-later
"""Run inside the real Blender interpreter; fail if any scene/file step fails."""
from pathlib import Path
import json
import sys
import bpy

arguments = sys.argv[sys.argv.index("--") + 1:]
output, startup = map(Path, arguments)
output.mkdir(parents=True, exist_ok=True)
assert bpy.app.version == (5, 2, 2), bpy.app.version

# The original startup fixture comes from the stable source release, with its
# original file schema rather than our new native layout.
bpy.ops.wm.open_mainfile(filepath=str(startup))
assert len(bpy.data.objects) >= 3
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_plane_add(size=2)
obj = bpy.context.object
obj.name = "iPad é"
assert len(obj.data.vertices) == 4 and len(obj.data.polygons) == 1
modifier = obj.modifiers.new("Offline solidify", "SOLIDIFY")
modifier.thickness = 0.25
graph = bpy.context.evaluated_depsgraph_get()
evaluated = obj.evaluated_get(graph)
mesh = evaluated.to_mesh()
assert len(mesh.vertices) == 8 and len(mesh.polygons) == 6
evaluated.to_mesh_clear()
del evaluated, mesh, graph

obj.location.x = 0
obj.keyframe_insert(data_path="location", index=0, frame=1)
obj.location.x = 2
obj.keyframe_insert(data_path="location", index=0, frame=3)
bpy.context.scene.frame_set(2)
assert abs(obj.location.x - 1) < 0.0001, obj.location.x

image = bpy.data.images.new("Offline pixels", width=8, height=8, alpha=True)
image.colorspace_settings.name = "Non-Color"
image.pixels[:] = [0.2, 0.4, 0.6, 1.0] * 64
image.file_format = "PNG"
image.filepath_raw = str(output / "pixels.png")
image.save()
readback = bpy.data.images.load(image.filepath_raw, check_existing=False)
readback.colorspace_settings.name = "Non-Color"
assert tuple(readback.size) == (8, 8)
assert all(abs(a - b) < 0.005 for a, b in zip(readback.pixels[:4], [0.2, 0.4, 0.6, 1.0]))
bpy.data.images.remove(readback)
bpy.data.images.remove(image)

filename = output / "offline-scene.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(filename), compress=False)
assert filename.read_bytes()[:12] == b"BLENDER_v502", filename.read_bytes()[:12]
del obj, modifier
bpy.ops.wm.open_mainfile(filepath=str(filename))
obj = bpy.data.objects["iPad é"]
assert len(obj.data.vertices) == 4
assert obj.modifiers[0].type == "SOLIDIFY" and abs(obj.modifiers[0].thickness - 0.25) < 0.0001
bpy.context.scene.frame_set(2)
assert abs(obj.location.x - 1) < 0.0001
(output / "result.json").write_text(json.dumps({"version": list(bpy.app.version),
    "original_startup_loaded": True, "modeling": True, "modifier": True,
    "animation": True, "image_io": True, "native_blend_roundtrip": True}))
print("BLENDER_CORE_SCENE_OK")
