#!/usr/bin/env python3
"""Flatten an accepted engine archive and add the engine-free update helper."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
import urllib.request
import zipfile

REPO='tntisthebomb/BlenderIpad'
HELPER_COMMIT='4f133a2419e7676918dd56fa6f5e6f1b765d91b9'
HELPER_SHA256='2a47794cb9f5b080542e00614ef3da44ea591574e715cf80d93ac1f89a471c4b'

def sha(data):return hashlib.sha256(data).hexdigest()

def github(path):
    headers={'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'}
    if os.environ.get('GITHUB_TOKEN'):headers['Authorization']='Bearer '+os.environ['GITHUB_TOKEN']
    with urllib.request.urlopen(urllib.request.Request('https://api.github.com/repos/'+REPO+path,headers=headers)) as response:
        return json.load(response)

def verify_origin(run,artifact,jobs,commit,run_id,artifact_id):
    assert re.fullmatch('[0-9a-f]{40}',commit), 'Invalid expected source commit'
    assert run['id']==run_id and run['head_sha']==commit, 'Build source differs'
    job=next((job for job in jobs['jobs'] if job['name']=='editor (cpu-cycles)'),None)
    required_steps={'Validate and record the exact editor assets','Package accepted editor and corresponding source','Upload experimental editor and corresponding source'}
    assert job and required_steps<={step['name'] for step in job['steps'] if step['conclusion']=='success'}, 'CPU Cycles acceptance/package/upload did not pass'
    assert artifact['id']==artifact_id and artifact['name']=='blender-editor-cpu-cycles-with-source', 'Wrong source artifact'
    assert artifact['workflow_run']['id']==run_id and artifact['workflow_run']['head_sha']==commit, 'Source artifact belongs to another build'
    assert not artifact['expired'], 'Corresponding source expired'
    expiry=datetime.fromisoformat(artifact['expires_at'].replace('Z','+00:00'))
    assert expiry>datetime.now(timezone.utc)+timedelta(days=31), 'Source must outlast the 30-day preview download'

def assemble(engine_zip,helper,root,destination,commit,run_id,artifact_id):
    assert not destination.exists(), 'Output directory already exists'
    source_url=f'https://github.com/{REPO}/actions/runs/{run_id}/artifacts/{artifact_id}'
    with zipfile.ZipFile(engine_zip) as archive:
        names=archive.namelist()
        assert len(names)==len(set(names)), 'Duplicate archive paths'
        assert all(not info.is_dir() and len(PurePosixPath(info.filename).parts)==1 and
                   not PurePosixPath(info.filename).is_absolute() and '\\' not in info.filename and
                   info.filename not in ('.','..') and (info.external_attr>>16)&0o170000!=0o120000
                   for info in archive.infolist()), 'Unsafe or nested engine archive'
        proof=json.loads(archive.read('editor-validation.json'))
        assert set(proof['render_engines'])=={'BLENDER_WORKBENCH','BLENDER_EEVEE','CYCLES'}, 'Incomplete engine acceptance'
        required={'float32_texel_load_helpers','depth_stencil_clear','float32_texel_load','indirect_instance_drawing','render_attachment_lifetime','eevee_shadow_viewports'}
        assert required<=set(proof['checks']), 'Required port regressions were not accepted'
        for name,digest in proof['tests'].items():
            path=root/name
            assert path.resolve().is_relative_to(root.resolve()) and path.is_file() and sha(path.read_bytes())==digest, 'Acceptance fixtures differ: '+name
        assert {'index.html','service-worker.js','blender-core.wasm','blender-core.js','blender-core.data'}<=set(proof['assets']), 'Missing engine assets'
        for name,digest in proof['assets'].items():
            with archive.open(name) as stream:
                actual=hashlib.file_digest(stream,'sha256').hexdigest()
            assert actual==digest, 'Accepted engine bytes differ: '+name
        helper_bytes=helper.read_bytes()
        assert sha(helper_bytes)==HELPER_SHA256, 'Updater differs from validated helper'
        destination.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='ipad-delivery-',dir=destination.parent) as temporary:
            export=Path(temporary)/'Blender-iPad';export.mkdir()
            archive.extractall(export)
            (export/'README-original.txt').write_bytes((export/'README.txt').read_bytes())
            (export/'ipad-update.html').write_bytes(helper_bytes)
            (export/'README.txt').write_text(f'''Blender 5.2.2 iPad preview — CPU Cycles and Eevee

Physical Safari stability is still awaiting device acceptance.

1. Close any old Blender tabs and Home Screen windows.
2. Extract this download once. In WorldWideWeb, select this extracted folder,
   the one containing index.html, service-worker.js and blender-core.wasm.
3. Keep WorldWideWeb visible beside Safari during installation.
4. Open http://localhost:8080/ipad-update.html directly. Choose Install or update
   offline files. This installs files without starting Blender.
5. After installation, close every Blender tab and Home Screen window, including
   the updater. Reopen http://localhost:8080/ and choose Start Blender.

Use your actual server port and path if different. Keep the same address for
saved projects. Do not clear Safari site data to force an update.
If the iPad becomes sluggish, close the editor rather than repeatedly reloading.
For an engine-free report, use http://localhost:8080/ipad-startup.html.

The engine files are unchanged from the accepted source build {commit}.
The runtime computes locally and can use its installed offline files.
Complete corresponding source, licenses and rebuild instructions:
{source_url}
Download the corresponding -source.tar.gz from that artifact.
The original engine README is preserved as README-original.txt.
The updater's complete source is the readable ipad-update.html file; its
validated source commit is {HELPER_COMMIT}.
''')
            (export/'delivery-manifest.json').write_text(json.dumps({'sourceCommit':commit,'acceptedRun':run_id,
                'correspondingSourceArtifact':artifact_id,'correspondingSourceURL':source_url,
                'acceptedAssets':proof['assets'],'helperSourceCommit':HELPER_COMMIT,'helperSHA256':HELPER_SHA256,
                'physicalSafariAccepted':False},indent=2)+'\n')
            for name,digest in proof['assets'].items():
                assert sha((export/name).read_bytes())==digest, 'Packaging modified accepted asset: '+name
            shutil.move(export,destination)
    return destination

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--input-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source-commit',required=True)
    parser.add_argument('--run-id',type=int,required=True)
    parser.add_argument('--source-artifact-id',type=int,required=True)
    args=parser.parse_args()
    run=github(f'/actions/runs/{args.run_id}')
    artifact=github(f'/actions/artifacts/{args.source_artifact_id}')
    jobs=github(f'/actions/runs/{args.run_id}/jobs?per_page=100')
    verify_origin(run,artifact,jobs,args.source_commit,args.run_id,args.source_artifact_id)
    engine=list(args.input_dir.rglob('BlenderIpad-5.2.2-editor-preview.zip'))
    sources=list(args.input_dir.rglob('BlenderIpad-5.2.2-editor-preview-source.tar.gz'))
    assert len(engine)==len(sources)==1, 'Expected one complete accepted engine/source pair'
    root=Path(__file__).resolve().parents[1]
    result=assemble(engine[0],Path(__file__).with_name('ipad-update.html'),root,args.output,
                    args.source_commit,args.run_id,args.source_artifact_id)
    print('Verified accepted engine bytes, matched fixtures and corresponding source; prepared',result)
