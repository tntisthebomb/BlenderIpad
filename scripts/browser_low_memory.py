"""Conservative post-link iPad profile; executable WASM sections stay identical."""
import hashlib

HEADER=b'\0asm\x01\0\0\0'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def u32(data, offset, end):
    value=0
    for shift in range(0,35,7):
        if offset>=end:raise ValueError('Truncated WASM integer')
        byte=data[offset];offset+=1
        if shift==28 and byte & 0xf0:raise ValueError('Oversized WASM integer')
        value|=(byte&0x7f)<<shift
        if not byte&0x80:return value,offset
    raise ValueError('Unterminated WASM integer')

def sections(data):
    if data[:8]!=HEADER:raise ValueError('Expected WASM version 1')
    offset=8
    while offset<len(data):
        begin=offset;kind=data[offset];offset+=1
        if kind>13:raise ValueError('Unknown WASM section')
        size,offset=u32(data,offset,len(data));end=offset+size
        if end>len(data):raise ValueError('Truncated WASM section')
        name=None
        if kind==0:
            length,start=u32(data,offset,end)
            if start+length>end:raise ValueError('Truncated custom section name')
            name=data[start:start+length].decode('utf-8')
        yield kind,name,data[begin:end]
        offset=end

def strip_debug_names(data):
    entries=list(sections(data))
    removed=[raw for kind,name,raw in entries if kind==0 and name=='name']
    if len(removed)!=1:raise ValueError('Expected exactly one name section')
    retained=[raw for kind,name,raw in entries if not(kind==0 and name=='name')]
    output=HEADER+b''.join(retained)
    if [raw for _,_,raw in sections(output)]!=retained:
        raise ValueError('Retained WASM sections changed')
    return output,{'removedCustomSection':'name','removedBytes':sum(map(len,removed)),
        'retainedSectionSHA256':[sha(raw) for raw in retained],
        'inputSHA256':sha(data),'outputSHA256':sha(output),
        'inputBytes':len(data),'outputBytes':len(output)}

DPR_IMPORT='''function _emscripten_get_device_pixel_ratio() {
  if (ENVIRONMENT_IS_PTHREAD) return proxyToMainThread(54, 0, 1);
  return devicePixelRatio;
}'''
CANVAS_RATIO_IMPORT='''function _emscripten_get_device_pixel_ratio() {
  if (ENVIRONMENT_IS_PTHREAD) return proxyToMainThread(54, 0, 1);
  if (Module["browserLowResource"] && Module["canvas"]?.clientWidth>0) {
    return Module["canvas"].width / Module["canvas"].clientWidth;
  }
  return devicePixelRatio;
}'''

def fix_tablet_pixel_ratio(text):
    if text.count(DPR_IMPORT)!=1:
        raise ValueError('Unrecognized original pixel-ratio import')
    return text.replace(DPR_IMPORT,CANVAS_RATIO_IMPORT)
