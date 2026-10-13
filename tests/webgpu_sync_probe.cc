/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <emscripten.h>
#include <webgpu/webgpu.h>
#ifdef BLENDER_SYNC_PYTHON
#  include <Python.h>
#endif
#include <cmath>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>

static WGPUInstance instance;
static WGPUAdapter adapter;
static WGPUDevice device;
static WGPUQueue queue;
static WGPUBuffer input, output, readback;
static WGPUComputePipeline pipeline;
static WGPUBindGroup bindings;
static std::string wgsl;
static int iteration = 0;
static bool failed = false;

static void fail(const char *message)
{
  failed = true;
  EM_ASM({ document.body.dataset.error = UTF8ToString($0); }, message);
}
static void fail(const char *context, WGPUStringView message)
{
  std::string detail(context);
  if (message.data) {
    detail += ": ";
    detail.append(message.data, message.length == WGPU_STRLEN ? std::strlen(message.data) : message.length);
  }
  fail(detail.c_str());
}
static void dispatch();
static void mapped(WGPUMapAsyncStatus status, WGPUStringView message, void *, void *)
{
  if (status != WGPUMapAsyncStatus_Success) { fail("native buffer mapping failed", message); return; }
  const auto *values = static_cast<const float *>(wgpuBufferGetConstMappedRange(readback, 0, 80));
  if (!values) { fail("native mapped range missing"); return; }
  const float expected[20] = {0.5f,0,0,0, -1.0f/6,1.0f/3,0,0, 0,0,0.25f,0, -1.5f,-2,-1.75f,1, 1,1,1,1};
  for (int i = 0; i < 20; i++) {
    const float wanted = iteration == 0 ? expected[i] : 0;
    if (!std::isfinite(values[i]) || std::fabs(values[i] - wanted) > 1e-6f) {
      fail("native GPU numerical readback mismatch"); return;
    }
  }
  wgpuBufferUnmap(readback);
  if (++iteration == 1) { dispatch(); return; }
  wgpuBindGroupRelease(bindings);
  wgpuComputePipelineRelease(pipeline);
  wgpuBufferRelease(input); wgpuBufferRelease(output); wgpuBufferRelease(readback);
  wgpuQueueRelease(queue); wgpuDeviceRelease(device);
  wgpuAdapterRelease(adapter); wgpuInstanceRelease(instance);
#ifndef BLENDER_SYNC_PYTHON
  if (!failed) EM_ASM({ document.body.dataset.done = 'true'; });
#endif
}
static void dispatch()
{
  const float matrix[16] = {2,0,0,0, 1,3,0,0, 0,0,4,0, 5,6,7,1};
  const float singular[16] = {};
  wgpuQueueWriteBuffer(queue, input, 0, iteration == 0 ? matrix : singular, 64);
  const WGPUCommandEncoder encoder = wgpuDeviceCreateCommandEncoder(device, nullptr);
  const WGPUComputePassEncoder pass = wgpuCommandEncoderBeginComputePass(encoder, nullptr);
  wgpuComputePassEncoderSetPipeline(pass, pipeline);
  wgpuComputePassEncoderSetBindGroup(pass, 0, bindings, 0, nullptr);
  wgpuComputePassEncoderDispatchWorkgroups(pass, 1, 1, 1);
  wgpuComputePassEncoderEnd(pass);
  wgpuComputePassEncoderRelease(pass);
  wgpuCommandEncoderCopyBufferToBuffer(encoder, output, 0, readback, 0, 80);
  const WGPUCommandBuffer commands = wgpuCommandEncoderFinish(encoder, nullptr);
  wgpuQueueSubmit(queue, 1, &commands);
  wgpuCommandBufferRelease(commands); wgpuCommandEncoderRelease(encoder);
  WGPUMapAsyncStatus mapping_status = WGPUMapAsyncStatus_Error;
  WGPUBufferMapCallbackInfo callback = WGPU_BUFFER_MAP_CALLBACK_INFO_INIT;
  callback.mode = WGPUCallbackMode_WaitAnyOnly;
  callback.userdata1 = &mapping_status;
  callback.callback = [](WGPUMapAsyncStatus status,WGPUStringView,void *userdata,void *) {
    *static_cast<WGPUMapAsyncStatus *>(userdata)=status;
  };
  const WGPUFuture future=wgpuBufferMapAsync(readback,WGPUMapMode_Read,0,80,callback);
  WGPUFutureWaitInfo wait={future,false};
  if (wgpuInstanceWaitAny(instance,1,&wait,UINT64_MAX)!=WGPUWaitStatus_Success) {
    fail("synchronous WebGPU future wait failed"); return;
  }
  mapped(mapping_status,{},nullptr,nullptr);
}
#ifdef BLENDER_SYNC_PYTHON
static PyObject *python_gpu_read(PyObject *,PyObject *)
{
  dispatch();
  if (failed) { PyErr_SetString(PyExc_RuntimeError,"GPU readback failed"); return nullptr; }
  Py_RETURN_TRUE;
}
static PyMethodDef gpu_methods[]={{"read",python_gpu_read,METH_NOARGS,"Real synchronous WebGPU readback"},{nullptr,nullptr,0,nullptr}};
static PyModuleDef gpu_module={PyModuleDef_HEAD_INIT,"native_gpu",nullptr,-1,gpu_methods};
static PyObject *initialize_gpu_module() { return PyModule_Create(&gpu_module); }
#endif
static WGPUBuffer buffer(uint64_t size, WGPUBufferUsage usage)
{
  WGPUBufferDescriptor descriptor = WGPU_BUFFER_DESCRIPTOR_INIT;
  descriptor.size = size; descriptor.usage = usage;
  return wgpuDeviceCreateBuffer(device, &descriptor);
}
static void pipeline_ready(WGPUCreatePipelineAsyncStatus status, WGPUComputePipeline result,
                           WGPUStringView message, void *, void *)
{
  if (status != WGPUCreatePipelineAsyncStatus_Success || !result) { fail("native compute pipeline failed", message); return; }
  pipeline = result;
  input = buffer(64, WGPUBufferUsage_Storage | WGPUBufferUsage_CopyDst);
  output = buffer(80, WGPUBufferUsage_Storage | WGPUBufferUsage_CopySrc);
  readback = buffer(80, WGPUBufferUsage_CopyDst | WGPUBufferUsage_MapRead);
  WGPUBindGroupEntry entries[2] = {WGPU_BIND_GROUP_ENTRY_INIT, WGPU_BIND_GROUP_ENTRY_INIT};
  entries[0].binding = 0; entries[0].buffer = output; entries[0].size = 80;
  entries[1].binding = 1; entries[1].buffer = input; entries[1].size = 64;
  const WGPUBindGroupLayout layout = wgpuComputePipelineGetBindGroupLayout(pipeline, 0);
  WGPUBindGroupDescriptor descriptor = WGPU_BIND_GROUP_DESCRIPTOR_INIT;
  descriptor.layout = layout; descriptor.entryCount = 2; descriptor.entries = entries;
  bindings = wgpuDeviceCreateBindGroup(device, &descriptor);
  wgpuBindGroupLayoutRelease(layout);
#ifdef BLENDER_SYNC_PYTHON
  if (PyRun_SimpleString("import native_gpu\nassert native_gpu.read() is True\n")!=0 || failed) {
    fail("actual CPython GPU callback failed"); return;
  }
  if (Py_FinalizeEx()!=0) { fail("Python finalization failed"); return; }
  EM_ASM({document.body.dataset.done='true';document.body.dataset.python='true';});
#else
  dispatch();
#endif
}
static void device_ready(WGPURequestDeviceStatus status, WGPUDevice result, WGPUStringView message, void *, void *)
{
  if (status != WGPURequestDeviceStatus_Success || !result) { fail("native WebGPU device unavailable", message); return; }
  device = result; queue = wgpuDeviceGetQueue(device);
  WGPUShaderSourceWGSL source = WGPU_SHADER_SOURCE_WGSL_INIT;
  source.code = {wgsl.c_str(), wgsl.size()};
  WGPUShaderModuleDescriptor shader_descriptor = WGPU_SHADER_MODULE_DESCRIPTOR_INIT;
  shader_descriptor.nextInChain = &source.chain;
  const WGPUShaderModule shader = wgpuDeviceCreateShaderModule(device, &shader_descriptor);
  WGPUComputePipelineDescriptor descriptor = WGPU_COMPUTE_PIPELINE_DESCRIPTOR_INIT;
  descriptor.compute.module = shader;
  WGPUCreateComputePipelineAsyncCallbackInfo callback = WGPU_CREATE_COMPUTE_PIPELINE_ASYNC_CALLBACK_INFO_INIT;
  callback.mode = WGPUCallbackMode_AllowSpontaneous; callback.callback = pipeline_ready;
  wgpuDeviceCreateComputePipelineAsync(device, &descriptor, callback);
  wgpuShaderModuleRelease(shader);
}
static void adapter_ready(WGPURequestAdapterStatus status, WGPUAdapter result, WGPUStringView message, void *, void *)
{
  if (status != WGPURequestAdapterStatus_Success || !result) { fail("native WebGPU adapter unavailable", message); return; }
  adapter = result;
  WGPUDeviceDescriptor descriptor = WGPU_DEVICE_DESCRIPTOR_INIT;
  descriptor.uncapturedErrorCallbackInfo.callback = [](WGPUDevice const *, WGPUErrorType, WGPUStringView message, void *, void *) { fail("native WebGPU validation error", message); };
  WGPURequestDeviceCallbackInfo callback = WGPU_REQUEST_DEVICE_CALLBACK_INFO_INIT;
  callback.mode = WGPUCallbackMode_AllowSpontaneous; callback.callback = device_ready;
  wgpuAdapterRequestDevice(adapter, &descriptor, callback);
}
int main()
{
#ifdef BLENDER_SYNC_PYTHON
  if (PyImport_AppendInittab("native_gpu",initialize_gpu_module)!=0) { fail("native Python module setup failed"); return 1; }
  PyConfig config; PyConfig_InitIsolatedConfig(&config);
  config.install_signal_handlers=0;config.site_import=0;config.parse_argv=0;
  PyStatus status=PyConfig_SetBytesString(&config,&config.home,"/python");
  if (!PyStatus_Exception(status)) status=PyConfig_SetBytesString(&config,&config.program_name,"/python/bin/python");
  if (!PyStatus_Exception(status)) status=Py_InitializeFromConfig(&config);
  PyConfig_Clear(&config);
  if (PyStatus_Exception(status)) {fail("actual Python initialization failed");return 1;}
#endif
  std::ifstream file("/blender-matrix.wgsl");
  if (!file) { fail("translated shader input missing"); return 1; }
  std::ostringstream text; text << file.rdbuf(); wgsl = text.str();
  WGPUInstanceFeatureName feature=WGPUInstanceFeatureName_TimedWaitAny;
  WGPUInstanceLimits limits=WGPU_INSTANCE_LIMITS_INIT;
  limits.timedWaitAnyMaxCount=8;
  WGPUInstanceDescriptor descriptor=WGPU_INSTANCE_DESCRIPTOR_INIT;
  descriptor.requiredFeatureCount=1; descriptor.requiredFeatures=&feature;
  descriptor.requiredLimits=&limits;
  instance = wgpuCreateInstance(&descriptor);
  WGPURequestAdapterCallbackInfo callback = WGPU_REQUEST_ADAPTER_CALLBACK_INFO_INIT;
  callback.mode = WGPUCallbackMode_AllowSpontaneous; callback.callback = adapter_ready;
  wgpuInstanceRequestAdapter(instance, nullptr, callback);
  return 0;
}
