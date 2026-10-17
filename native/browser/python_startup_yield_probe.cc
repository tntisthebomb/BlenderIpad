/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <Python.h>
#include <emscripten.h>
#include "webgpu/startup_yield.hh"

static int chunk_ms = 25;
EM_JS(void, mark_probe, (int complete), {
  Module['pythonProbeCompleted'] = !!complete;
});

static PyObject *cooperate(PyObject *, PyObject *args)
{
  int value;
  if (!PyArg_ParseTuple(args, "i", &value)) return nullptr;
  volatile int cookie = value * 37 + 17;
  const double until = emscripten_get_now() + chunk_ms;
  while (emscripten_get_now() < until) {}
  blender_browser_startup_cooperate();
  if (cookie != value * 37 + 17) {
    PyErr_SetString(PyExc_RuntimeError, "Native stack changed during Python suspension");
    return nullptr;
  }
  return PyLong_FromLong(value * 11 + 3);
}

static PyObject *round_trip(PyObject *, PyObject *args)
{
  PyObject *callback;
  int value;
  if (!PyArg_ParseTuple(args, "Oi", &callback, &value)) return nullptr;
  volatile int cookie = value * 7 + 1;
  PyObject *argument = PyLong_FromLong(value);
  if (!argument) return nullptr;
  PyObject *result = PyObject_CallOneArg(callback, argument);
  Py_DECREF(argument);
  if (cookie != value * 7 + 1) {
    Py_XDECREF(result);
    PyErr_SetString(PyExc_RuntimeError, "Nested callback stack changed during suspension");
    return nullptr;
  }
  return result;
}

static PyMethodDef methods[] = {
  {"cooperate", cooperate, METH_VARARGS, nullptr},
  {"round_trip", round_trip, METH_VARARGS, nullptr},
  {nullptr, nullptr, 0, nullptr}
};
static PyModuleDef definition = {
  PyModuleDef_HEAD_INIT, "_browser_coop_probe", nullptr, -1, methods
};
PyMODINIT_FUNC PyInit__browser_coop_probe() { return PyModule_Create(&definition); }

extern "C" int probe_initialize()
{
  if (Py_IsInitialized()) return 1;
  if (PyImport_AppendInittab("_browser_coop_probe", PyInit__browser_coop_probe) == -1) return 0;
  PyConfig config;
  PyConfig_InitIsolatedConfig(&config);
  config.install_signal_handlers = 0;
  config.site_import = 0;
  config.parse_argv = 0;
  PyStatus status = PyConfig_SetBytesString(&config, &config.home, "/python");
  if (!PyStatus_Exception(status)) status = PyConfig_SetBytesString(&config, &config.program_name, "/python/bin/python");
  if (!PyStatus_Exception(status)) status = Py_InitializeFromConfig(&config);
  PyConfig_Clear(&config);
  return !PyStatus_Exception(status);
}

extern "C" int probe_execute(int milliseconds)
{
  chunk_ms = milliseconds;
  mark_probe(0);
  const int result = PyRun_SimpleString(R"py(
import _browser_coop_probe as p
def recurse(depth, value):
    if depth:
        return p.round_trip(lambda x: recurse(depth-1, x), value) + 1
    return p.cooperate(value)
for i in range(48):
    assert recurse(3, i) == i*11+6
)py");
  mark_probe(1);
  return result;
}
