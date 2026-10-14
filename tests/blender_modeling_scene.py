"""Actual modeling, geometry nodes, rigging and desktop-format interchange."""
import bpy
import json
import math
from mathutils import Vector
from pathlib import Path

output=Path('/modeling-output');output.mkdir(exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add()
mesh=bpy.context.object
mesh.name='Modeling acceptance'
# Real edit-mode operators must mutate Blender's mesh, not a JS scene model.
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
assert bpy.ops.mesh.subdivide(number_cuts=1)=={'FINISHED'}
bpy.ops.object.mode_set(mode='OBJECT')
assert len(mesh.data.vertices)==26
assert mesh.data.validate() is False
bevel=mesh.modifiers.new('Bevel acceptance','BEVEL')
bevel.width=0.1;bevel.segments=2
bpy.context.view_layer.update()
evaluated=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
assert len(evaluated.vertices)>26 and len(evaluated.polygons)>24
mesh.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh_clear()
mesh.modifiers.remove(bevel)
# Geometry-node execution checks real field graph evaluation and coordinates.
tree=bpy.data.node_groups.new('Browser geometry acceptance','GeometryNodeTree')
tree.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry')
tree.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
source=tree.nodes.new('NodeGroupInput');sink=tree.nodes.new('NodeGroupOutput')
transform=tree.nodes.new('GeometryNodeTransform')
transform.inputs['Translation'].default_value=(2,0,0)
tree.links.new(source.outputs['Geometry'],transform.inputs['Geometry'])
tree.links.new(transform.outputs['Geometry'],sink.inputs['Geometry'])
modifier=mesh.modifiers.new('Geometry nodes acceptance','NODES');modifier.node_group=tree
bpy.context.view_layer.update()
eval_object=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
evaluated=eval_object.to_mesh()
centroid=sum((vertex.co for vertex in evaluated.vertices),Vector())/len(evaluated.vertices)
assert (centroid-Vector((2,0,0))).length<1e-5,tuple(centroid)
eval_object.to_mesh_clear()
# An armature must deform the evaluated mesh; pose values alone are insufficient.
bpy.ops.mesh.primitive_cube_add();rigged=bpy.context.object;rigged.name='Rigged acceptance'
bpy.ops.object.armature_add();rig=bpy.context.object
modifier=rigged.modifiers.new('Armature acceptance','ARMATURE');modifier.object=rig
rigged.vertex_groups.new(name='Bone').add(list(range(8)),1.0,'REPLACE')
rig.pose.bones['Bone'].location=(0,0,1)
bpy.context.view_layer.update()
eval_object=rigged.evaluated_get(bpy.context.evaluated_depsgraph_get());evaluated=eval_object.to_mesh()
centroid=sum((vertex.co for vertex in evaluated.vertices),Vector())/8
assert math.isclose(centroid.length,1.0,abs_tol=1e-5),tuple(centroid)
eval_object.to_mesh_clear()
# Native OBJ export and import preserve actual evaluated geometry offline.
bpy.ops.object.select_all(action='DESELECT');mesh.select_set(True)
bpy.context.view_layer.objects.active=mesh
assert bpy.ops.wm.obj_export(filepath=str(output/'scene.obj'),export_selected_objects=True)=={'FINISHED'}
assert (output/'scene.obj').read_text().count('\nv ')>=26
assert bpy.ops.wm.obj_import(filepath=str(output/'scene.obj'))=={'FINISHED'}
imported=bpy.context.view_layer.objects.active
assert len(imported.data.vertices)==26
assert math.isclose(min(vertex.co.x for vertex in imported.data.vertices),1.0,abs_tol=1e-5)
# Preserve node/rig resources and external-format results in a native project.
project=output/'workflows.blend'
assert bpy.ops.wm.save_as_mainfile(filepath=str(project),check_existing=False)=={'FINISHED'}
assert bpy.ops.wm.open_mainfile(filepath=str(project))=={'FINISHED'}
assert bpy.data.objects.get('Rigged acceptance') and bpy.data.node_groups.get('Browser geometry acceptance')
(output/'result.json').write_text(json.dumps({'version':list(bpy.app.version),
    'checks':['edit_mesh','bevel','geometry_nodes','armature_deformation','obj_roundtrip','native_resources']}))
print('PASS: native edit mesh, bevel, geometry nodes, armature deformation, OBJ interchange and native project resources.')
