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
for label, colour, hidden in (
    ('red', (1, 0, 0, 1), False),
    ('green', (0, 1, 0, 1), False),
    ('empty', (0, 1, 0, 1), True),
):
    cube.color = colour
    material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = colour
    cube.hide_render = hidden
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
        target = 0 if label == 'red' else 1
        assert sum(p[target] for p in opaque) > sum(p[1 - target] for p in opaque) * 2
    results[label] = {'opaque_pixels': len(opaque)}
    bpy.data.images.remove(image)
with open('/render-output/result.json', 'w') as stream:
    json.dump({'version': list(bpy.app.version), 'engine': engine, 'checks': results}, stream)
print('PASS: native scene rendering, PNG content, material colours and hidden-object visibility.')
