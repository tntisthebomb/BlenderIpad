#include <Python.h>
#include <assert.h>
#include <emscripten.h>
#include <stdio.h>

static PyObject *suspend_probe(PyObject *self, PyObject *args)
{
  (void)self;
  (void)args;
  emscripten_sleep(1);
  Py_RETURN_NONE;
}

static PyMethodDef methods[] = {{"wait", suspend_probe, METH_NOARGS, NULL}, {NULL}};
static struct PyModuleDef module = {PyModuleDef_HEAD_INIT, "suspend_probe", NULL, -1, methods};
static PyObject *initialize_probe(void) { return PyModule_Create(&module); }

int main(void)
{
  assert(PyImport_AppendInittab("suspend_probe", initialize_probe) == 0);
  PyConfig config;
  PyConfig_InitIsolatedConfig(&config);
  config.install_signal_handlers = 0;
  config.site_import = 0;
  PyStatus status = PyConfig_SetBytesString(&config, &config.home, "/python");
  assert(!PyStatus_Exception(status));
  status = Py_InitializeFromConfig(&config);
  assert(!PyStatus_Exception(status));
  PyConfig_Clear(&config);
  int result = PyRun_SimpleString(
      "import json, decimal, xml.etree.ElementTree as E, suspend_probe\n"
      "class Value:\n"
      " def __init__(self, n): self.n = n\n"
      "def recurse(n):\n"
      " if n == 0:\n"
      "  suspend_probe.wait()\n"
      "  return Value(7).n\n"
      " return recurse(n - 1) + Value(1).n\n"
      "for i in range(3):\n"
      " assert recurse(64) == 71\n"
      " assert json.loads(json.dumps({'value': i}))['value'] == i\n"
      " assert str(decimal.Decimal('0.1') + decimal.Decimal('0.2')) == '0.3'\n"
      " assert E.fromstring('<scene><mesh/></scene>')[0].tag == 'mesh'\n");
  assert(result == 0);
  assert(Py_FinalizeEx() == 0);
  puts("PASS: CPython imports, class calls, recursion and repeated suspension");
  return 0;
}
