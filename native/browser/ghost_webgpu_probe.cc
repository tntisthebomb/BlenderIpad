/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "GHOST_ISystem.hh"
#include "GHOST_IWindow.hh"
#include "GHOST_ContextWebGPU.hh"
#include "CLG_log.h"
#include <emscripten.h>
#include <cmath>
#include <cstdio>
#include <cstring>

static GHOST_ISystem *system_instance;
static GHOST_IWindow *window_instance;
static WGPUInstance instance;
static WGPUAdapter adapter;
static WGPUDevice device;
static int frames;
static int pending;
static void fail(const char *message) { EM_ASM({document.body.dataset.error ||= UTF8ToString($0);},message); }
static void fail(const char *prefix,WGPUStringView message)
{
  char text[2048];
  snprintf(text,sizeof(text),"%s: %.*s",prefix,int(message.length==WGPU_STRLEN ? strlen(message.data ? message.data : "") : message.length),message.data ? message.data : "");
  fail(text);
}
static GHOST_IWindow *open_window()
{
  GHOST_GPUSettings settings = {};
  settings.context_type = GHOST_kDrawingContextTypeWebGPU;
  auto *window=system_instance->createWindow("Blender WebGPU GHOST context",0,0,64,48,
      GHOST_kWindowStateNormal,settings,false,false,nullptr);
  if (window && GHOST_Context::getActiveDrawingContext()!=window->getDrawingContext()) {
    fail("new graphics window was not activated");
    system_instance->disposeWindow(window);
    return nullptr;
  }
  return window;
}
struct Readback { WGPUBuffer buffer; int red, green, blue; bool bgra; };
static void mapped(WGPUMapAsyncStatus status, WGPUStringView message, void *user, void *)
{
  auto *read = static_cast<Readback *>(user);
  if (status != WGPUMapAsyncStatus_Success) { fail("surface pixel mapping failed",message); }
  else {
    const auto *pixel = static_cast<const unsigned char *>(wgpuBufferGetConstMappedRange(read->buffer,0,256));
    if (!pixel || std::abs(int(pixel[read->bgra ? 2 : 0])-read->red)>1 ||
        std::abs(int(pixel[1])-read->green)>1 ||
        std::abs(int(pixel[read->bgra ? 0 : 2])-read->blue)>1 || pixel[3]!=255)
      fail("surface pixel readback mismatch");
    else EM_ASM({document.body.dataset.frames=String($0);},++frames);
    wgpuBufferUnmap(read->buffer);
  }
  wgpuBufferRelease(read->buffer); delete read; --pending;
}
extern "C" int ghost_gpu_frame(int alternate)
{
  if (!window_instance || window_instance->activateDrawingContext()!=GHOST_kSuccess) return 0;
  auto *context=static_cast<GHOST_ContextWebGPU *>(window_instance->getDrawingContext());
  if (window_instance->swapBufferRelease()!=GHOST_kFailure ||
      window_instance->swapBufferAcquire()!=GHOST_kSuccess ||
      window_instance->swapBufferAcquire()!=GHOST_kFailure ||
      window_instance->swapBufferRelease()!=GHOST_kFailure) return 0;
  const auto encoder=wgpuDeviceCreateCommandEncoder(device,nullptr);
  WGPURenderPassColorAttachment color=WGPU_RENDER_PASS_COLOR_ATTACHMENT_INIT;
  color.view=context->view(); color.loadOp=WGPULoadOp_Clear; color.storeOp=WGPUStoreOp_Store;
  color.clearValue=alternate ? WGPUColor{0.75,0.25,0.125,1} : WGPUColor{0.125,0.5,0.75,1};
  WGPURenderPassDescriptor pass_descriptor=WGPU_RENDER_PASS_DESCRIPTOR_INIT;
  pass_descriptor.colorAttachmentCount=1; pass_descriptor.colorAttachments=&color;
  auto pass=wgpuCommandEncoderBeginRenderPass(encoder,&pass_descriptor);
  wgpuRenderPassEncoderEnd(pass); wgpuRenderPassEncoderRelease(pass);
  WGPUBufferDescriptor buffer_descriptor=WGPU_BUFFER_DESCRIPTOR_INIT;
  buffer_descriptor.size=256; buffer_descriptor.usage=WGPUBufferUsage_CopyDst|WGPUBufferUsage_MapRead;
  auto *read=new Readback{wgpuDeviceCreateBuffer(device,&buffer_descriptor),
    alternate ? 191 : 32, alternate ? 64 : 128, alternate ? 32 : 191,
    context->format()==WGPUTextureFormat_BGRA8Unorm};
  WGPUTexelCopyTextureInfo source=WGPU_TEXEL_COPY_TEXTURE_INFO_INIT;
  source.texture=context->texture();
  WGPUTexelCopyBufferInfo destination=WGPU_TEXEL_COPY_BUFFER_INFO_INIT;
  destination.buffer=read->buffer; destination.layout.bytesPerRow=256;
  const WGPUExtent3D size={1,1,1};
  wgpuCommandEncoderCopyTextureToBuffer(encoder,&source,&destination,&size);
  const auto command=wgpuCommandEncoderFinish(encoder,nullptr);
  const bool submitted=context->submit(command)==GHOST_kSuccess;
  wgpuCommandBufferRelease(command); wgpuCommandEncoderRelease(encoder);
  if (!submitted || window_instance->swapBufferRelease()!=GHOST_kSuccess ||
      window_instance->swapBufferRelease()!=GHOST_kFailure) return 0;
  WGPUBufferMapCallbackInfo callback=WGPU_BUFFER_MAP_CALLBACK_INFO_INIT;
  callback.mode=WGPUCallbackMode_AllowSpontaneous; callback.callback=mapped; callback.userdata1=read;
  ++pending;
  wgpuBufferMapAsync(read->buffer,WGPUMapMode_Read,0,256,callback);
  return 1;
}
extern "C" int ghost_gpu_pending() { return pending; }
extern "C" int ghost_gpu_close()
{
  if (!window_instance) return 0;
  const bool disposed=system_instance->disposeWindow(window_instance)==GHOST_kSuccess;
  window_instance=nullptr; return disposed;
}
extern "C" int ghost_gpu_reopen()
{
  if (window_instance) return 0;
  window_instance=open_window(); return window_instance!=nullptr;
}
extern "C" int ghost_gpu_shutdown()
{
  if (window_instance) ghost_gpu_close();
  GHOST_ContextWebGPU::setBootstrap(nullptr,nullptr);
  GHOST_ISystem::disposeSystem(); system_instance=nullptr;
  wgpuDeviceRelease(device); wgpuAdapterRelease(adapter); wgpuInstanceRelease(instance);
  device=nullptr; adapter=nullptr; instance=nullptr;
  CLG_exit(); return 1;
}
static void device_ready(WGPURequestDeviceStatus status,WGPUDevice result,WGPUStringView,void*,void*)
{
  if (status!=WGPURequestDeviceStatus_Success || !result) {fail("WebGPU device unavailable");return;}
  device=result; GHOST_ContextWebGPU::setBootstrap(instance,device);
  window_instance=open_window();
  if (!window_instance) {fail("real GHOST WebGPU window creation failed");return;}
  EM_ASM({document.body.dataset.ready='true';});
}
static void adapter_ready(WGPURequestAdapterStatus status,WGPUAdapter result,WGPUStringView,void*,void*)
{
  if (status!=WGPURequestAdapterStatus_Success || !result) {fail("WebGPU adapter unavailable");return;}
  adapter=result;
  WGPUDeviceDescriptor descriptor=WGPU_DEVICE_DESCRIPTOR_INIT;
  descriptor.uncapturedErrorCallbackInfo.callback=[](WGPUDevice const*,WGPUErrorType,WGPUStringView message,void*,void*) {fail("WebGPU validation error",message);};
  WGPURequestDeviceCallbackInfo callback=WGPU_REQUEST_DEVICE_CALLBACK_INFO_INIT;
  callback.mode=WGPUCallbackMode_AllowSpontaneous; callback.callback=device_ready;
  wgpuAdapterRequestDevice(adapter,&descriptor,callback);
}
int main()
{
  CLG_init();
  if (GHOST_ISystem::createSystem(true,false)!=GHOST_kSuccess) {fail("GHOST system failed");return 1;}
  system_instance=GHOST_ISystem::getSystem();
  // Creating a GPU window without actual device bootstrap must fail cleanly.
  if (open_window()) {fail("uninitialized graphics window was accepted");return 1;}
  instance=wgpuCreateInstance(nullptr);
  WGPURequestAdapterCallbackInfo callback=WGPU_REQUEST_ADAPTER_CALLBACK_INFO_INIT;
  callback.mode=WGPUCallbackMode_AllowSpontaneous; callback.callback=adapter_ready;
  wgpuInstanceRequestAdapter(instance,nullptr,callback); return 0;
}
