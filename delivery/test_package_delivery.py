"""Small packaging fixtures only; this does not execute Blender."""
import importlib.util
import json
from pathlib import Path
import tempfile
from datetime import datetime,timedelta,timezone
import zipfile
spec=importlib.util.spec_from_file_location('delivery',Path(__file__).with_name('package_delivery.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def rejected(call,message):
    try:call()
    except (AssertionError,KeyError):return
    raise AssertionError('Accepted invalid fixture: '+message)

commit='a'*40
run={'id':1,'head_sha':commit}
artifact={'id':2,'name':'blender-editor-cpu-cycles-with-source','expired':False,'expires_at':(datetime.now(timezone.utc)+timedelta(days=89)).isoformat(), 'workflow_run':{'id':1,'head_sha':commit}}
steps=[{'name':name,'conclusion':'success'} for name in ['Validate and record the exact editor assets','Package accepted editor and corresponding source','Upload experimental editor and corresponding source']]
jobs={'jobs':[{'name':'editor (cpu-cycles)','conclusion':None,'steps':steps}]}
m.verify_origin(run,artifact,jobs,commit,1,2)
rejected(lambda:m.verify_origin({**run,'head_sha':'b'*40},artifact,jobs,commit,1,2),'source commit')
rejected(lambda:m.verify_origin(run,{**artifact,'expired':True},jobs,commit,1,2),'expired source')
rejected(lambda:m.verify_origin(run,artifact,{'jobs':[]},commit,1,2),'no accepted profile')
rejected(lambda:m.verify_origin(run,artifact,{'jobs':[{'name':'editor (cpu-cycles)','steps':steps[:2]}]},commit,1,2),'missing upload')
with tempfile.TemporaryDirectory(prefix='delivery-test-') as temporary:
    root=Path(temporary);(root/'tests').mkdir();(root/'tests/fixture.py').write_text('# Packaging fixture only\n')
    assets={name:b'Not a Blender engine; packaging fixture only' for name in ['index.html','service-worker.js','blender-core.wasm','blender-core.js','blender-core.data']}
    proof={'render_engines':['BLENDER_WORKBENCH','BLENDER_EEVEE','CYCLES'],
        'checks':['float32_texel_load_helpers','depth_stencil_clear','float32_texel_load','indirect_instance_drawing','render_attachment_lifetime','eevee_shadow_viewports'],
        'tests':{'tests/fixture.py':m.sha((root/'tests/fixture.py').read_bytes())},'assets':{name:m.sha(data) for name,data in assets.items()}}
    def make(name,mutate=None,extra=None):
        path=root/name
        with zipfile.ZipFile(path,'w') as archive:
            for name,data in assets.items():archive.writestr(name,b'Changed bytes' if name==mutate else data)
            archive.writestr('README.txt','Packaging fixture only')
            archive.writestr('editor-validation.json',json.dumps(proof))
            if extra:archive.writestr(extra,'Unsafe fixture')
        return path
    good=make('accepted-fixture.zip');helper=Path(__file__).with_name('ipad-update.html')
    dest=root/'ready'
    m.assemble(good,helper,root,dest,commit,1,2)
    assert all((dest/name).read_bytes()==data for name,data in assets.items())
    assert (dest/'ipad-update.html').read_bytes()==helper.read_bytes()
    assert json.loads((dest/'delivery-manifest.json').read_text())['physicalSafariAccepted'] is False
    rejected(lambda:m.assemble(make('changed.zip',mutate='blender-core.wasm'),helper,root,root/'changed',commit,1,2),'changed engine')
    rejected(lambda:m.assemble(make('unsafe.zip',extra='../escape'),helper,root,root/'unsafe',commit,1,2),'unsafe archive path')
    altered=root/'altered-helper.html';altered.write_bytes(helper.read_bytes()+b'changed')
    rejected(lambda:m.assemble(good,altered,root,root/'altered',commit,1,2),'changed updater')
    (root/'tests/fixture.py').write_text('# Changed fixture\n')
    rejected(lambda:m.assemble(good,helper,root,root/'fixture',commit,1,2),'changed acceptance fixture')
    assert not any((root/name).exists() for name in ['changed','unsafe','altered','fixture','escape'])
print('PASS: packaging fixtures preserve engine bytes, add the pinned updater, enforce accepted build/source metadata, and reject tampering or unsafe paths. No engine was executed.')
