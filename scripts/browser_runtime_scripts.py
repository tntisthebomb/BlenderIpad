"""Stage Blender's upstream scripts, including enabled delayed-install add-ons."""
from pathlib import Path
import shutil
import tempfile
from setup_browser import CACHE


def stage_runtime_scripts(core):
    source = CACHE / 'blender-browser'
    configuration = (core / 'CMakeCache.txt').read_text().splitlines()
    cycles = 'WITH_CYCLES:BOOL=ON' in configuration
    # Use a fresh derived snapshot so profile changes cannot leave a disabled
    # add-on behind or overwrite a previous snapshot's local edits.
    destination = Path(tempfile.mkdtemp(prefix='runtime-scripts-', dir=CACHE)) / 'scripts'
    shutil.copytree(source / 'scripts', destination)
    if cycles:
        # Upstream CMake delayed_install puts these files in addons_core/cycles.
        # Compiling bf_intern_cycles alone does not install its Python engine.
        shutil.copytree(source / 'intern/cycles/blender/addon',
                        destination / 'addons_core/cycles')
    return destination
