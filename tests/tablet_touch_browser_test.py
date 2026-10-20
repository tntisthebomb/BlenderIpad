#!/usr/bin/env python3
"""A second finger must cancel selection intent without losing tap/drag ends."""
import argparse,os,shutil
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--browser',choices=('chromium','webkit'),default='chromium')
args=parser.parse_args()
class Handler(SimpleHTTPRequestHandler):
 def log_message(self,*a):pass
with TemporaryDirectory(dir=ROOT/'.cache',prefix='touch-intent-') as tmp:
 base=Path(tmp);shutil.copyfile(ROOT/'native/browser/tablet_touch.js',base/'tablet_touch.js')
 (base/'index.html').write_text('''<!doctype html><canvas id="canvas"></canvas><script src="tablet_touch.js"></script><script>
 const canvas=document.getElementById('canvas');window.nativeTouchEvents=[];
 installBlenderTabletTouch(canvas,true);
 for(const type of ['touchstart','touchmove','touchend','touchcancel'])canvas.addEventListener(type,event=>{
  nativeTouchEvents.push({type,touches:Array.from(event.touches,t=>t.identifier),changed:Array.from(event.changedTouches,t=>t.identifier)});
 });
 window.emitTouch=(type,ids,changed)=>{
  const point=id=>({identifier:id,target:canvas,clientX:50+id*20,clientY:70,pageX:50+id*20,pageY:70,screenX:50+id*20,screenY:70});
  const event=new Event(type,{bubbles:true,cancelable:true});
  for(const [key,value] of Object.entries({touches:ids.map(point),targetTouches:ids.map(point),changedTouches:changed.map(point)})){
   Object.defineProperty(event,key,{value});
  }
  canvas.dispatchEvent(event);return event.defaultPrevented;
 };
 </script>''')
 server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=tmp));Thread(target=server.serve_forever,daemon=True).start()
 try:
  with sync_playwright() as p:
   browser=getattr(p,args.browser).launch(**({'executable_path':os.environ.get('CHROMIUM_PATH','/usr/lib/chromium/chromium'),'args':['--no-sandbox']} if args.browser=='chromium' else {}))
   page=browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto(f'http://127.0.0.1:{server.server_port}/')
   assert page.evaluate("emitTouch('touchstart',[1],[1])")
   assert page.evaluate('nativeTouchEvents.length')==0,'First finger selected before gesture intent was known'
   page.evaluate("emitTouch('touchstart',[1,2],[2]);emitTouch('touchmove',[1,2],[1,2]);emitTouch('touchend',[2],[1]);emitTouch('touchend',[],[2])")
   seen=page.evaluate('nativeTouchEvents')
   assert [e['type'] for e in seen]==['touchstart','touchmove','touchend','touchend'],seen
   assert seen[0]['touches']==seen[0]['changed']==[1,2],seen
   assert page.evaluate('blenderTabletTouchReport.cancelledSelectionPresses')==1
   page.evaluate("nativeTouchEvents=[];emitTouch('touchstart',[3],[3]);emitTouch('touchend',[],[3])")
   assert page.evaluate('nativeTouchEvents.map(e=>e.type)')==['touchstart','touchend']
   page.evaluate("nativeTouchEvents=[];emitTouch('touchstart',[4],[4]);emitTouch('touchmove',[4],[4]);emitTouch('touchend',[],[4])")
   assert page.evaluate('nativeTouchEvents.map(e=>e.type)')==['touchstart','touchmove','touchend']
   page.evaluate("nativeTouchEvents=[];emitTouch('touchstart',[5],[5]);emitTouch('touchcancel',[],[5])")
   assert page.evaluate('nativeTouchEvents.length')==0
   page.evaluate("emitTouch('touchstart',[6],[6])")
   page.wait_for_function('nativeTouchEvents.length===1')
   page.evaluate("emitTouch('touchend',[],[6])")
   assert page.evaluate('nativeTouchEvents.map(e=>e.type)')==['touchstart','touchend']
   assert not errors,errors
   browser.close()
 finally:server.shutdown();server.server_close()
print('PASS: '+args.browser+' two-finger intent prevents the initial selection press; taps, single-finger drags, held presses, finger release and cancellation are preserved (event-routing fixture).')
