"""Observe and exercise actual editor state; called only by browser acceptance."""
import bpy
bpy.context.preferences.view.show_splash=False
import json
from pathlib import Path

command=Path('/editor-command.json')
state=Path('/editor-state.json')
errors=[]
last_operation=None
observations=0

def observe():
    global last_operation, observations
    observations += 1
    try:
        if command.exists():
            request=json.loads(command.read_text())
            command.unlink()
            path=request['path']
            assert path.startswith('/projects/') and '..' not in Path(path).parts
            if request['operation']=='save':
                assert bpy.ops.wm.save_as_mainfile(filepath=path,check_existing=False)=={'FINISHED'}
            elif request['operation']=='load':
                assert bpy.ops.wm.open_mainfile(filepath=path)=={'FINISHED'}
            elif request['operation']=='deselect':
                for obj in bpy.context.view_layer.objects:
                    obj.select_set(False)
            else:
                raise ValueError(request['operation'])
            last_operation=request['operation']
        windows=bpy.context.window_manager.windows
        active=windows[0].view_layer.objects.active if windows else None
        position=None
        view=None
        if windows and active:
            from bpy_extras.view3d_utils import location_3d_to_region_2d
            for area in windows[0].screen.areas:
                if area.type!='VIEW_3D': continue
                region=next(region for region in area.regions if region.type=='WINDOW')
                view={'rotation':list(area.spaces.active.region_3d.view_rotation),
                      'distance':area.spaces.active.region_3d.view_distance,
                      'region':[region.x,region.y,region.width,region.height]}
                point=location_3d_to_region_2d(region,area.spaces.active.region_3d,active.matrix_world.translation)
                if point:
                    position=[region.x+point.x,region.y+point.y]
                break
        state.write_text(json.dumps({
            'version':list(bpy.app.version),
            'observations':observations,
            'backend':__import__('gpu').platform.backend_type_get(),
            'windows':len(windows),
            'areas':[area.type for area in windows[0].screen.areas] if windows else [],
            'active':active.name if active else None,
            'location':list(active.location) if active else None,
            'mode':active.mode if active else None,
            'selected':[obj.name for obj in windows[0].view_layer.objects if obj.select_get()] if windows else [],
            'object_position':position,
            'view':view,
            'filepath':bpy.data.filepath,
            'last_operation':last_operation,
            'errors':errors,
        }))
    except Exception as error:
        errors.append(str(error))
        state.write_text(json.dumps({'errors':errors}))
    return 0.1

bpy.app.timers.register(observe,first_interval=0.2,persistent=True)
