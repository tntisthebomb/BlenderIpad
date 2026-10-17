#!/usr/bin/env python3
"""Compile the exact native startup-yield helper with the actual Asyncify policy."""
from setup_browser import ROOT,CACHE,toolchain,run
if __name__=='__main__':
 env=toolchain();out=CACHE/'startup-yield-probe';out.mkdir(exist_ok=True)
 run('em++',ROOT/'native/browser/startup_yield_probe.cc','-O2','-sASYNCIFY=1','-sASSERTIONS=2',
  '-sASYNCIFY_IMPORTS=@'+str(ROOT/'cmake/python-asyncify-imports.json'),
  '-sENVIRONMENT=web','-sMODULARIZE=1','-sEXPORT_NAME=createYieldProbe','-o',out/'probe.js',env=env)
 (out/'index.html').write_text('''<!doctype html><meta charset="utf-8"><body><script>
 window.ticks=0;window.paints=0;setInterval(()=>ticks++,5);
 function paint(){paints++;requestAnimationFrame(paint);}requestAnimationFrame(paint);
 </script><script src="probe.js"></script><script>
 createYieldProbe({browserCooperativeStartup:true,onAbort:message=>document.body.dataset.error=String(message)});
 </script></body>''')
