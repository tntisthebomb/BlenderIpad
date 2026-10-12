#!/usr/bin/env python3
"""Build real GHOST canvas graphics in a separate opt-in development profile."""
from setup_browser import CACHE, ROOT, toolchain, prepare_source, run
if __name__ == '__main__':
    env=toolchain()
    source=prepare_source()
    build=CACHE/'ghost-webgpu-build'
    run('emcmake','cmake','-S',ROOT/'native/browser','-B',build,'-G','Ninja',
        '-DBLENDER_SOURCE_DIR='+str(source),'-DWITH_GHOST_WEBGPU_CONTEXT=ON',env=env)
    run('cmake','--build',build,'--parallel','4',env=env)
