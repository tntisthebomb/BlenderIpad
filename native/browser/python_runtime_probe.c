/* SPDX-License-Identifier: GPL-2.0-or-later */
/* C-API integration test for Blender's CPython dependency, not a bpy substitute. */
#include <Python.h>
#include <stdio.h>
#include <string.h>

static char error_message[512];

int python_runtime_initialize(void)
{
  if (Py_IsInitialized()) return 1;
  PyConfig config;
  PyConfig_InitIsolatedConfig(&config);
  config.install_signal_handlers = 0;
  config.site_import = 0;
  config.parse_argv = 0;
  PyStatus status = PyConfig_SetBytesString(&config, &config.home, "/python");
  if (!PyStatus_Exception(status)) {
    status = PyConfig_SetBytesString(&config, &config.program_name, "/python/bin/python");
  }
  if (!PyStatus_Exception(status)) status = Py_InitializeFromConfig(&config);
  if (PyStatus_Exception(status)) {
    snprintf(error_message, sizeof(error_message), "%s", status.err_msg ? status.err_msg : "Python initialization failed");
  }
  PyConfig_Clear(&config);
  return !PyStatus_Exception(status);
}

const char *python_runtime_error(void) { return error_message; }

int python_runtime_execute(const char *script)
{
  if (!Py_IsInitialized()) return -2;
  return PyRun_SimpleString(script);
}

int python_runtime_finalize(void)
{
  return Py_IsInitialized() ? Py_FinalizeEx() : 0;
}
