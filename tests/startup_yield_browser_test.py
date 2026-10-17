#!/usr/bin/env python3
"""Require timer/paint opportunities and intact native state across real suspension."""
import argparse,os,json
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--browser',default='chromium',choices=('chromium','webkit'));args=p.parse_args()
class Handler(SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(ROOT/'.cache/startup-yield-probe')));Thread(target=server.serve_forever,daemon=True).start()
try:
 with sync_playwright() as p:
  browser=getattr(p,args.browser).launch(**({'executable_path':os.environ.get('CHROMIUM_PATH','/usr/lib/chromium/chromium'),'args':['--no-sandbox']} if args.browser=='chromium' else {}))
  page=browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(f'http://127.0.0.1:{server.server_port}/');page.wait_for_function('document.body.dataset.done || document.body.dataset.error')
  assert not page.evaluate('document.body.dataset.error'),page.evaluate('document.body.dataset.error')
  assert not errors,errors
  result=page.evaluate('yieldProbeResult');print('PASS: '+args.browser+' real native repeated suspension, preserved stack/state and timer/paint opportunities '+json.dumps(result),flush=True)
  browser.close()
finally:server.shutdown();server.server_close()
