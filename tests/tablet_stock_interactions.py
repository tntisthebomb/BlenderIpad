"""Drive stock Blender through its UI; inspect results through its native console."""
import json
from pathlib import Path

def exercise_stock_editor(page,context,output):
 output=Path(output);sequence=0
 page.set_default_timeout(120000)
 page.locator('#toggle-startup-stats').click()
 page.mouse.move(450,320);page.locator('#canvas').focus()
 page.keyboard.press('Escape');page.keyboard.press('Escape')
 # Ordinary stock startup has no injected timer, scene script, or command file.
 # Use the real Console editor solely to observe the result of native UI input.
 def inspect(label,save=False):
  nonlocal sequence
  sequence+=1;path=f'/stock-interaction-{sequence}.json'
  page.mouse.move(450,320);page.keyboard.press('Shift+F4')
  body="""def _stock_snapshot():
 import bpy,json
 from pathlib import Path
 from bpy_extras.view3d_utils import location_3d_to_region_2d
 v=next(s for s in bpy.context.area.spaces if s.type=='VIEW_3D')
 r=next(r for r in bpy.context.area.regions if r.type=='WINDOW')
 o=bpy.data.objects['Cube']
 p=location_3d_to_region_2d(r,v.region_3d,o.matrix_world.translation)
 Path(PATH_VALUE).write_text(json.dumps({'mode':o.mode,'selected':o.select_get(),'location':list(o.location),'rotation':list(v.region_3d.view_rotation),'distance':v.region_3d.view_distance,'region':[r.x,r.y,r.width,r.height],'position':list(p) if p else None}))
_stock_snapshot()
del _stock_snapshot
""".replace('PATH_VALUE',repr(path))
  compile(body,'stock-observer','exec')
  command='exec('+repr(body)+')'
  if save:command="import bpy; bpy.ops.wm.save_as_mainfile(filepath='/projects/tablet-stock-interaction.blend',compress=False); "+command
  page.keyboard.type(command,delay=1);page.keyboard.press('Enter')
  try:page.wait_for_function('path=>blenderEditor.FS.analyzePath(path).exists',arg=path,timeout=45000)
  except Exception:
   print('STOCK_UI_FAILURE '+label+' '+str(page.evaluate('({errors:editorErrors,output:editorOutput.slice(-8),stats:blenderStartupStats.snapshot()})')),flush=True)
   page.locator('#canvas').screenshot(path=str(output/f'stock-interaction-{label}-failure.png'));raise
  state=json.loads(page.evaluate('path=>blenderEditor.FS.readFile(path,{encoding:"utf8"})',path))
  print('STOCK_UI '+label+' '+json.dumps(state),flush=True)
  page.keyboard.press('Shift+F5')
  assert not page.evaluate('document.body.dataset.error'),page.evaluate('editorErrors')
  return state
 initial=inspect('initial')
 box=page.locator('#canvas').bounding_box();scale=page.evaluate('canvas.width/canvas.clientWidth')
 region=initial['region'];position=initial['position'];assert position,initial
 page.mouse.move(450,320);page.keyboard.press('Alt+a')
 page.touchscreen.tap(box['x']+(region[0]+position[0])/scale,
  box['y']+box['height']-(region[1]+position[1])/scale)
 selected=inspect('selected');assert selected['selected'],selected
 page.evaluate('''()=>{
  window.stockTouchAudit=[];
  for(const type of ['touchstart','touchend','mousedown','mouseup','pointerdown','pointerup']){
   window.addEventListener(type,event=>{
    if(stockTouchAudit.length<40)stockTouchAudit.push({type:event.type,pointerType:event.pointerType,
      touchMouse:event.sourceCapabilities?.firesTouchEvents,touches:event.touches?.length,x:event.clientX,y:event.clientY});
   },{capture:true,passive:true});
  }
 }''')
 session=context.new_cdp_session(page)
 cx=box['x']+(region[0]+region[2]*.5)/scale
 cy=box['y']+box['height']-(region[1]+region[3]*.5)/scale
 for repeat in range(3):
  points=lambda offset:[{'id':1,'x':cx-40+offset,'y':cy},{'id':2,'x':cx+40+offset,'y':cy}]
  session.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':points(0)})
  for offset in (12,24,36):session.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':points(offset)})
  session.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
 def measure_orbit(label):
  # Warmed viewport interactions must batch offscreen work into few submissions.
  # Count the real device queue, retaining the application's existing wrapper.
  page.evaluate("""()=>{
   const device=blenderEditor.preinitializedWebGPUDevice,queue=device.queue,submit=queue.submit,create=device.createBuffer;
   window.stockOrbitGPU={submits:0,presents:0,buffers:0,bufferBytes:0};
   device.createBuffer=function(d){stockOrbitGPU.buffers++;stockOrbitGPU.bufferBytes+=d.size;return Reflect.apply(create,this,[d]);};
   queue.submit=function(commands){
    stockOrbitGPU.submits++;
    stockOrbitGPU.presents+=Array.from(commands).filter(c=>c.label==='Blender present').length;
    return Reflect.apply(submit,this,[commands]);
   };
   window.restoreStockOrbitQueue=()=>{queue.submit=submit;device.createBuffer=create;};
  }""")
  try:
   for repeat in range(3):
    points=lambda offset:[{'id':1,'x':cx-40+offset,'y':cy},{'id':2,'x':cx+40+offset,'y':cy}]
    session.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':points(0)})
    for offset in (12,24,36):
     session.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':points(offset)})
     page.wait_for_timeout(40)
    session.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
   page.wait_for_timeout(500)
   orbit_gpu=page.evaluate('stockOrbitGPU')
  finally:page.evaluate('restoreStockOrbitQueue()')
  print('STOCK_ORBIT_GPU '+label+' '+json.dumps(orbit_gpu),flush=True)
  assert orbit_gpu['presents']>=3,'Repeated orbit did not present real native frames'
  assert orbit_gpu['submits']<=4*orbit_gpu['presents'],orbit_gpu
  assert orbit_gpu['buffers']<=40*orbit_gpu['presents'],orbit_gpu
  return orbit_gpu
 orbit_gpu=measure_orbit('object-mode')
 orbited=inspect('orbited')
 print('STOCK_TOUCH_AUDIT '+json.dumps(page.evaluate('stockTouchAudit')),flush=True)
 assert any(abs(a-b)>.001 for a,b in zip(selected['rotation'],orbited['rotation'])),(selected,orbited)
 assert orbited['selected'],'Two-finger orbit unexpectedly changed native selection'
 # Re-select at the projected native position before testing transform input.
 # Keep the post-orbit selection state in the diagnostic result as well.
 position=orbited['position'];region=orbited['region']
 page.touchscreen.tap(box['x']+(region[0]+position[0])/scale,
  box['y']+box['height']-(region[1]+position[1])/scale)
 page.mouse.move(cx,cy);page.locator('#canvas').focus()
 for key in ('g','x','1','Enter'):page.keyboard.press(key)
 moved=inspect('translated');assert abs(moved['location'][0]-1)<.001,moved
 page.mouse.move(cx,cy);page.keyboard.press('Tab')
 edited=inspect('edit-mode');assert edited['mode']=='EDIT',edited
 edit_orbit_gpu=measure_orbit('edit-mode')
 page.mouse.move(cx,cy);page.keyboard.press('Tab')
 final=inspect('object-mode',save=True);assert final['mode']=='OBJECT' and final['selected'],final
 page.locator('#canvas').screenshot(path=str(output/'stock-interaction-final.png'))
 assert not page.evaluate('editorErrors.length'),page.evaluate('editorErrors')
 return {'orbitGPU':orbit_gpu,'editOrbitGPU':edit_orbit_gpu,'initial':initial,'selected':selected,'orbited':orbited,'translated':moved,'edited':edited,'final':final}
