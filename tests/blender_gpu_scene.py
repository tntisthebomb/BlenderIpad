"""Actual Blender GPU resources, builtin shaders and batch drawing acceptance."""
import bpy
import gpu
import json
import math
import os
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix

assert bpy.app.version == (5,2,2)
gpu.init()
assert gpu.platform.backend_type_get() == 'WEBGPU'

def flattened(value):
    if isinstance(value,(int,float)):
        yield float(value)
    else:
        for child in value: yield from flattened(child)

checks={}
expected=[0.25,0.5,0.75,1.0]*64
for name in ['RGBA8','RGBA16F','RGBA32F']:
    data=gpu.types.Buffer('FLOAT',len(expected),expected)
    texture=gpu.types.GPUTexture((8,8),format=name,data=data)
    actual=list(flattened(texture.read()))
    # Blender's public API returns bytes for UNORM8 texture readback.
    if name=='RGBA8': actual=[value/255 for value in actual]
    assert len(actual)==len(expected),(name,len(actual))
    tolerance=1/255 if name=='RGBA8' else 1e-6
    assert all(math.isclose(a,b,rel_tol=0,abs_tol=tolerance) for a,b in zip(actual,expected)),(name,actual[:8])
    checks[name]=True

# Distinct layer colours ensure readback does not silently return only layer 0.
for label,options,layers in [
    ('array_layers',{'size':(8,8),'layers':3},3),
    ('cube_faces',{'size':8,'is_cubemap':True},6),
]:
    values=[]
    for layer in range(layers): values += [layer/(layers-1),0.25,0.75,1.0]*64
    texture=gpu.types.GPUTexture(format='RGBA8',data=gpu.types.Buffer('FLOAT',len(values),values),**options)
    actual=list(flattened(texture.read()))
    actual=[value/255 for value in actual]
    assert len(actual)==len(values),(label,len(actual),len(values))
    assert all(math.isclose(a,b,rel_tol=0,abs_tol=1/255) for a,b in zip(actual,values)),label
    checks[label]=True

offscreen=gpu.types.GPUOffScreen(32,32,format='RGBA8')
with offscreen.bind():
    framebuffer=gpu.state.active_framebuffer_get()
    framebuffer.clear(color=(0,0,0,1))
    gpu.matrix.load_matrix(Matrix.Identity(4))
    gpu.matrix.load_projection_matrix(Matrix.Identity(4))
    gpu.state.depth_test_set('NONE')
    gpu.state.blend_set('NONE')
    shader=gpu.shader.from_builtin('UNIFORM_COLOR')
    batch=batch_for_shader(shader,'TRIS',{'pos':[(-1,-1,0),(1,-1,0),(0,1,0)]})
    shader.bind()
    shader.uniform_float('color',(1,0,0,1))
    batch.draw(shader)
    pixel=list(flattened(framebuffer.read_color(16,16,1,1,4,0,'FLOAT')))
    assert len(pixel)==4,pixel
    assert all(math.isclose(a,b,rel_tol=0,abs_tol=1/255) for a,b in zip(pixel,[1,0,0,1])),pixel
    corner=list(flattened(framebuffer.read_color(0,16,1,1,4,0,'FLOAT')))
    assert all(math.isclose(a,b,rel_tol=0,abs_tol=1/255) for a,b in zip(corner,[0,0,0,1])),corner
    checks['builtin_shader_triangle']=True
offscreen.free()
# Font glyphs use the storage-buffer shader whose translated block variable
# can become `S`. Verify the real font renderer produces pixels, rather than
# checking only the create-info mapping in isolation.
import blf
font=blf.load('/blender/datafiles/fonts/Inter.woff2')
assert font>=0,font
offscreen=gpu.types.GPUOffScreen(128,32,format='RGBA8')
with offscreen.bind():
    framebuffer=gpu.state.active_framebuffer_get()
    framebuffer.clear(color=(0,0,0,1))
    gpu.matrix.load_matrix(Matrix.Identity(4))
    gpu.matrix.load_projection_matrix(Matrix((
        (2/128,0,0,-1),(0,2/32,0,-1),(0,0,-1,0),(0,0,0,1))))
    gpu.state.depth_test_set('NONE')
    gpu.state.blend_set('ALPHA')
    blf.size(font,16)
    blf.position(font,4,8,0)
    blf.color(font,1,1,1,1)
    blf.draw(font,'Blender')
    pixels=list(flattened(framebuffer.read_color(0,0,128,32,4,0,'FLOAT')))
    lit=sum(max(pixels[index:index+3])>0.25 for index in range(0,len(pixels),4))
    assert 20<lit<128*32/2,lit
    checks['font_storage_shader']=True
offscreen.free()
blf.unload('/blender/datafiles/fonts/Inter.woff2')
os.makedirs('/gpu-output',exist_ok=True)
with open('/gpu-output/result.json','w') as stream:
    json.dump({'version':list(bpy.app.version),'checks':checks},stream)
print('PASS: actual Blender GPU texture upload/readback, font rendering, builtin shader, uniforms, vertex batch and framebuffer draw/readback.')
