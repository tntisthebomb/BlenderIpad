"""Actual Blender GPU resources, builtin shaders and batch drawing acceptance."""
import bpy
import gpu
import json
import math
import os
import struct
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

# Eevee's packed HDR images use portable padded storage in WebGPU. Exercise
# public upload and packed readback, including the exact logical buffer size.
hdr_values=[1.0,0.5,0.25]*64
texture=gpu.types.GPUTexture((8,8),format='R11F_G11F_B10F',
    data=gpu.types.Buffer('FLOAT',len(hdr_values),hdr_values))
actual=list(flattened(texture.read()))
half=lambda value: struct.unpack('<H',struct.pack('<e',value))[0]
packed=(half(1.0)>>4) | ((half(0.5)>>4)<<11) | ((half(0.25)>>5)<<22)
assert len(actual)==64 and all(value==packed for value in actual),(len(actual),actual[:8])
checks['packed_hdr']=True

# Include equal-sized source/destination encodings: RG float32 uploads have
# eight bytes per pixel, just like the padded four-component half-float target.
for name,components in [('R16F',1),('RG16F',2)]:
    values=[0.25,0.5][:components]*64
    texture=gpu.types.GPUTexture((8,8),format=name,data=gpu.types.Buffer('FLOAT',len(values),values))
    actual=list(flattened(texture.read()))
    assert len(actual)==len(values),(name,len(actual))
    assert all(math.isclose(a,b,rel_tol=0,abs_tol=1e-6) for a,b in zip(actual,values)),(name,actual[:8])
    info=gpu.types.GPUShaderCreateInfo()
    info.local_group_size(8,8)
    info.image(0,name,'FLOAT_2D','target',qualifiers={'WRITE'})
    info.compute_source('void main(){imageStore(target,ivec2(gl_GlobalInvocationID.xy),vec4(0.5,0.25,0.75,1.0));}')
    shader=gpu.shader.create_from_info(info)
    shader.image('target',texture)
    gpu.compute.dispatch(shader,1,1,1)
    actual=list(flattened(texture.read()))
    expected=[0.5,0.25][:components]*64
    assert actual==expected,(name,actual[:8])
    gpu.shader.unbind()
    checks[name+'_storage']=True

# Exercise the translator corrections through the packaged native backend.
for name,components in [('R16',1),('RG16',2),('RGBA16',4)]:
    values=[0.12345,0.54321,0.8,1.0][:components]*64
    texture=gpu.types.GPUTexture((8,8),format=name,data=gpu.types.Buffer('FLOAT',len(values),values))
    actual=list(flattened(texture.read()))
    quantized=lambda value: math.floor(max(0,min(1,value))*65535+0.5)/65535
    assert len(actual)==len(values),(name,len(actual))
    assert all(abs(a-quantized(b))<1e-7 for a,b in zip(actual,values)),(name,actual[:8])
    info=gpu.types.GPUShaderCreateInfo()
    info.local_group_size(8,8)
    info.image(0,name,'FLOAT_2D','target',qualifiers={'WRITE'})
    info.compute_source('void main(){imageStore(target,ivec2(gl_GlobalInvocationID.xy),vec4(0.12345,-0.5,2.0,0.54321));}')
    shader=gpu.shader.create_from_info(info)
    shader.image('target',texture)
    gpu.compute.dispatch(shader,1,1,1)
    actual=list(flattened(texture.read()))
    expected=[0.12345,0,1,0.54321][:components]*64
    assert all(abs(a-quantized(b))<1e-7 for a,b in zip(actual,expected)),(name,actual[:8])
    gpu.shader.unbind()
    checks[name+'_storage']=True

info=gpu.types.GPUShaderCreateInfo()
info.local_group_size(1,1)
info.image(0,'RGBA32F','FLOAT_2D','target',qualifiers={'WRITE'})
info.compute_source('''
int calculate(int selector) {
  int value=1;
  switch(selector) {
    case 0: value+=2;
    case 1: value*=3; break;
    case 2: if(selector>=1 && selector<4) value+=5;
    case 3: for(int i=0;i<7;i++) value++; break;
    default: value=-5;
  }
  return value;
}
void main() {
  imageStore(target,ivec2(gl_GlobalInvocationID.xy),
             vec4(float(calculate(int(gl_GlobalInvocationID.x))),0,0,1));
}''')
shader=gpu.shader.create_from_info(info)
target=gpu.types.GPUTexture((6,1),format='RGBA32F')
shader.image('target',target)
gpu.compute.dispatch(shader,6,1,1)
assert list(flattened(target.read()))[::4]==[9,3,13,8,-5,-5]
gpu.shader.unbind()
checks['switch_fallthrough']=True

info=gpu.types.GPUShaderCreateInfo()
info.local_group_size(1,1)
info.sampler(0,'FLOAT_3D','volume_texture')
info.image(1,'RGBA32F','FLOAT_2D','target',qualifiers={'WRITE'})
info.compute_source('''void main(){
  ivec3 dimensions=textureSize(volume_texture,0);
  float texel=round(texelFetch(volume_texture,ivec3(1,2,3),0).r*255.0);
  imageStore(target,ivec2(0),vec4(vec3(dimensions),texel));
}''')
values=[0.0]*(2*3*4*4);values[92]=42/255
volume=gpu.types.GPUTexture((2,3,4),format='RGBA8',
    data=gpu.types.Buffer('FLOAT',len(values),values))
shader=gpu.shader.create_from_info(info)
target=gpu.types.GPUTexture((1,1),format='RGBA32F')
shader.uniform_sampler('volume_texture',volume)
shader.image('target',target)
gpu.compute.dispatch(shader,1,1,1)
assert list(flattened(target.read()))==[2,3,4,42]
gpu.shader.unbind()
checks['volume_query']=True

# Run this fixture on a device without optional float32-filterable support.
# Reuse a shader across filterable/unfilterable inputs to exercise layout keys.
info=gpu.types.GPUShaderCreateInfo()
info.local_group_size(1,1)
info.sampler(0,'FLOAT_2D','source_texture')
info.image(0,'RGBA32F','FLOAT_2D','target',qualifiers={'WRITE'})
info.compute_source('void main(){imageStore(target,ivec2(0),textureLod(source_texture,vec2(0.75),0.0));}')
shader=gpu.shader.create_from_info(info)
target=gpu.types.GPUTexture((1,1),format='RGBA32F')
shader.image('target',target)
for iteration,format_name in enumerate(['RGBA8','RGBA32F','RGBA8','RGBA32F']):
    values=[0.0]*12+[0.25+iteration*0.125,0.5,0.75,1.0]
    source=gpu.types.GPUTexture((2,2),format=format_name,
        data=gpu.types.Buffer('FLOAT',16,values))
    source.filter_mode(False)
    target.clear(format='FLOAT',value=(0,0,0,0))
    shader.uniform_sampler('source_texture',source)
    gpu.compute.dispatch(shader,1,1,1)
    actual=list(flattened(target.read()))
    assert all(abs(a-b)<1/255 for a,b in zip(actual,values[-4:])),(format_name,actual)
gpu.shader.unbind()
checks['float32_nearest_sampling']=True

# RGBA read/write images must work without texture-formats-tier2. Preserve
# padded rows, array layers, half-float packing and buffer/texture coherence.
for name in ['RGBA16F','RGBA32F']:
    initial=[0.25,0.5,-0.75,1.0]*8
    image=gpu.types.GPUTexture((2,2),layers=2,format=name,
        data=gpu.types.Buffer('FLOAT',len(initial),initial))
    info=gpu.types.GPUShaderCreateInfo()
    info.local_group_size(1,1)
    info.image(0,name,'FLOAT_2D_ARRAY','target',qualifiers={'READ','WRITE'})
    info.compute_source('''void main(){
      ivec3 p=ivec3(1,1,1);
      imageStore(target,p,imageLoad(target,p)+vec4(0.125));
    }''')
    shader=gpu.shader.create_from_info(info)
    shader.image('target',image)
    for count in [1,2]:
        gpu.compute.dispatch(shader,1,1,1)
        actual=list(flattened(image.read()))
        expected=initial[:-4]+[v+count*0.125 for v in initial[-4:]]
        assert actual==expected,(name,count,actual)
    gpu.shader.unbind()
checks['buffered_image_coherence']=True

# Eevee's virtual shadow atlas needs contended atomic min/add and coherent
# texture readback, followed by a normal texture write and another atomic pass.
atlas=gpu.types.GPUTexture((4,1),layers=1,format='R32UI')
info=gpu.types.GPUShaderCreateInfo()
info.local_group_size(1,1)
info.image(0,'R32UI','UINT_2D_ARRAY','atlas',qualifiers={'WRITE'})
info.compute_source('''void main(){
  imageStore(atlas,ivec3(0,0,0),uvec4(0xffffffffu));
  imageStore(atlas,ivec3(1,0,0),uvec4(0u));
}''')
clear_shader=gpu.shader.create_from_info(info)
clear_shader.image('atlas',atlas)
gpu.compute.dispatch(clear_shader,1,1,1)
gpu.shader.unbind()
info=gpu.types.GPUShaderCreateInfo()
info.local_group_size(64,1)
info.image(0,'R32UI','UINT_2D_ARRAY','atlas',qualifiers={'READ','WRITE'})
info.compute_source('''void main(){
  uint index=gl_GlobalInvocationID.x;
  imageAtomicMin(atlas,ivec3(0,0,0),1024u-index);
  imageAtomicAdd(atlas,ivec3(1,0,0),1u);
  imageAtomicMin(atlas,ivec3(0,0,-1),0u);
  imageAtomicAdd(atlas,ivec3(0,0,1),1u);
  if(index==0u) {
    imageStore(atlas,ivec3(2,0,0),uvec4(imageLoad(atlas,ivec3(0,0,0)).w));
    imageStore(atlas,ivec3(3,0,0),uvec4(imageLoad(atlas,ivec3(0,0,-1)).w));
  }
}''')
atomic_shader=gpu.shader.create_from_info(info)
atomic_shader.image('atlas',atlas)
gpu.compute.dispatch(atomic_shader,16,1,1)
assert list(flattened(atlas.read()))==[1,1024,1,0]
gpu.shader.unbind()
gpu.compute.dispatch(clear_shader,1,1,1)
gpu.shader.unbind()
atomic_shader.image('atlas',atlas)
gpu.compute.dispatch(atomic_shader,16,1,1)
assert list(flattened(atlas.read()))==[1,1024,1,0]
gpu.shader.unbind()
checks['atomic_image_coherence']=True

# Recycled native shader addresses must not retain another format or program.
import gc
for iteration in range(8):
    name='R16F' if iteration%2==0 else 'RGBA32F'
    value=(iteration+1)/8
    info=gpu.types.GPUShaderCreateInfo()
    info.local_group_size(1,1)
    info.image(0,name,'FLOAT_2D','target',qualifiers={'WRITE'})
    info.compute_source('void main(){imageStore(target,ivec2(0),vec4('+str(value)+'));}')
    ephemeral=gpu.shader.create_from_info(info)
    target=gpu.types.GPUTexture((1,1),format=name)
    ephemeral.image('target',target)
    gpu.compute.dispatch(ephemeral,1,1,1)
    assert all(component==value for component in flattened(target.read()))
    gpu.shader.unbind()
    del ephemeral,target,info
    gc.collect()
checks['shader_lifetime_cache']=True

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

# Depth and stencil are independent aspects. Keep these resources alive so
# the browser harness can verify both aspects directly after native execution.
stencil_targets=[]
for width,stencil_value,depth_value,clear_depth,clear_stencil in (
    (17,90,0.25,0.75,None),
    (19,165,0.25,None,60),
    (21,123,0.5,None,None),
):
    depth_texture=gpu.types.GPUTexture((width,13),format='DEPTH32F_STENCIL8')
    framebuffer=gpu.types.GPUFrameBuffer(depth_slot=depth_texture)
    with framebuffer.bind():
        framebuffer.clear(depth=depth_value,stencil=stencil_value)
        if clear_depth is not None:
            framebuffer.clear(depth=clear_depth)
        if clear_stencil is not None:
            framebuffer.clear(stencil=clear_stencil)
    stencil_targets.append((depth_texture,framebuffer))
checks['depth_stencil_clear']=True

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
