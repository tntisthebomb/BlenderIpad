"""Render real native scenes; validate image content and object visibility."""
import bpy
import gpu
import json
import math
import os
import sys

engine = sys.argv[sys.argv.index('--') + 1]
assert engine in {'BLENDER_WORKBENCH', 'BLENDER_EEVEE', 'CYCLES'}
gpu.init()
scene = bpy.context.scene
scene.render.engine = engine
if engine == 'CYCLES':
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 4
    scene.cycles.use_denoising = False
elif engine == 'BLENDER_EEVEE':
    scene.eevee.taa_render_samples = 8
scene.render.resolution_x = 64
scene.render.resolution_y = 64
scene.render.resolution_percentage = 100
scene.render.film_transparent = True
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.view_settings.view_transform = 'Standard'
scene.display.shading.light = 'FLAT'
scene.display.shading.color_type = 'OBJECT'
scene.display.render_aa = '8'
cube = bpy.data.objects['Cube']
material = bpy.data.materials.new('Render acceptance material')
material.use_nodes = True
cube.data.materials.clear()
cube.data.materials.append(material)
os.makedirs('/render-output', exist_ok=True)
results = {}
def render_and_verify(label, target, hidden=False):
    scene.render.filepath = '/render-output/' + label + '.png'
    assert bpy.ops.render.render(write_still=True) == {'FINISHED'}
    with open(scene.render.filepath, 'rb') as stream:
        assert stream.read(8) == b'\x89PNG\r\n\x1a\n'
    image = bpy.data.images.load(scene.render.filepath, check_existing=False)
    assert tuple(image.size) == (64, 64), tuple(image.size)
    pixels = list(image.pixels)
    assert len(pixels) == 64 * 64 * 4 and all(math.isfinite(v) for v in pixels)
    opaque = [pixels[i:i + 4] for i in range(0, len(pixels), 4) if pixels[i + 3] > 0.9]
    if hidden:
        assert not opaque, len(opaque)
    else:
        assert 50 < len(opaque) < 64 * 64 / 2, len(opaque)
        assert sum(p[target] for p in opaque) > sum(p[1 - target] for p in opaque) * 2
    results[label] = {'opaque_pixels': len(opaque)}
    bpy.data.images.remove(image)
for label, colour, hidden in (
    ('red', (1, 0, 0, 1), False),
    ('green', (0, 1, 0, 1), False),
    ('empty', (0, 1, 0, 1), True),
):
    cube.color = colour
    material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = colour
    cube.hide_render = hidden
    render_and_verify(label, 0 if label == 'red' else 1, hidden)

if engine != 'BLENDER_WORKBENCH':
    # Remove direct lights so these pixels require actual world-probe lighting.
    # Rough metal samples filtered probe mips; diffuse checks the SH reduction.
    cube.hide_render = False
    for obj in scene.objects:
        if obj.type == 'LIGHT':
            obj.hide_render = True
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get('Background')
    background.inputs['Strength'].default_value = 1
    bsdf = material.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (0.8, 0.8, 0.8, 1)
    bsdf.inputs['Roughness'].default_value = 0.85
    for kind, metallic in (('specular', 1), ('diffuse', 0)):
        bsdf.inputs['Metallic'].default_value = metallic
        for colour, target in (((1, 0, 0, 1), 0), ((0, 1, 0, 1), 1)):
            background.inputs['Color'].default_value = colour
            label = 'world_' + kind + ('_red' if target == 0 else '_green')
            render_and_verify(label, target)
            image = bpy.data.images.load(scene.render.filepath, check_existing=False)
            values = list(image.pixels)
            energy = sum(values[i + target] for i in range(0, len(values), 4) if values[i + 3] > 0.9)
            assert energy > results[label]['opaque_pixels'] * 0.05, (label, energy)
            bpy.data.images.remove(image)

if engine == 'BLENDER_EEVEE':
    # Identical geometry with shadows enabled/disabled must produce a darker
    # receiver. Test both local-light tiles and directional clip-map amendment.
    background.inputs['Color'].default_value = (0, 0, 0, 1)
    bsdf.inputs['Metallic'].default_value = 0
    bsdf.inputs['Base Color'].default_value = (0.8, 0.8, 0.8, 1)
    bsdf.inputs['Roughness'].default_value = 1
    cube.location = (0, 0, 1)
    cube.scale = (0.5, 0.5, 0.5)
    camera = scene.camera
    camera.location = (0, 0, 10)
    camera.rotation_euler = (0, 0, 0)
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = 8
    bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, 0))
    bpy.context.object.data.materials.append(material)
    for kind in ('SUN', 'POINT'):
        light_data = bpy.data.lights.new('Shadow acceptance ' + kind, kind)
        light = bpy.data.objects.new(light_data.name, light_data)
        scene.collection.objects.link(light)
        light.location = (3, 0, 6)
        light.rotation_euler = (0, math.pi / 4, 0)
        light_data.energy = 3 if kind == 'SUN' else 1500
        if kind == 'SUN':
            light_data.angle = 0.01
        else:
            light_data.shadow_soft_size = 0.05
        images = []
        for enabled in (False, True):
            light_data.use_shadow = enabled
            label = 'shadow_' + kind.lower() + ('_on' if enabled else '_off')
            scene.render.filepath = '/render-output/' + label + '.png'
            assert bpy.ops.render.render(write_still=True) == {'FINISHED'}
            image = bpy.data.images.load(scene.render.filepath, check_existing=False)
            pixels = list(image.pixels)
            assert tuple(image.size) == (64, 64) and all(math.isfinite(v) for v in pixels)
            opaque_count = sum(pixels[i + 3] > 0.9 for i in range(0, len(pixels), 4))
            assert opaque_count > 1000, (kind, opaque_count)
            results[label] = {'opaque_pixels': opaque_count}
            images.append(pixels)
            bpy.data.images.remove(image)
        darkened = sum(images[0][i] - images[1][i] > 0.05 and images[0][i + 3] > 0.9
                       for i in range(0, len(images[0]), 4))
        assert darkened > 8, (kind, 'shadow did not darken receiver', darkened)
        results['shadow_' + kind.lower() + '_on']['darkened_pixels'] = darkened
        light.hide_render = True

with open('/render-output/result.json', 'w') as stream:
    json.dump({'version': list(bpy.app.version), 'engine': engine, 'checks': results}, stream)
print('PASS: native scene rendering, PNG content, material colours and hidden-object visibility.')
