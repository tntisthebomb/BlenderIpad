/* SPDX-License-Identifier: GPL-2.0-or-later */
#pragma once

#include "shader_prepare.hh"
#include <algorithm>
#include <stdexcept>
#include <unordered_map>

namespace blender::gpu::webgpu_prepare {

/* RGBA read/write storage textures require texture-formats-tier2, which the
 * target iPad does not expose. Preserve their packed texels in a storage buffer
 * with the same copy layout as atomic images. Three write-only Eevee outputs
 * also use this path to fit the four-storage-texture WebGPU minimum; no output
 * is discarded. The backend synchronizes these mirrors before texture access. */
inline std::string lower_buffer_images(const std::string &source)
{
  const auto ts=tokens(source);
  struct Edit { size_t begin,end; std::string text; };
  std::vector<Edit> edits;
  std::unordered_set<std::string> names;
  for(size_t i=1;i+1<ts.size();i++) {
    if(ts[i+1].text!=";") continue;
    const auto &type=ts[i-1].text;
    const bool is2d=type=="image2D" || type=="uimage2D" || type=="iimage2D";
    if(!is2d && type!="image2DArray" && type!="image3D" &&
       type!="uimage2DArray" && type!="uimage3D" &&
       type!="iimage2DArray" && type!="iimage3D") continue;
    size_t start=i-1;
    while(start && ts[start].text!="layout" && ts[start-1].text!=";" && ts[start-1].text!="}") start--;
    if(ts[start].text!="layout") continue;
    bool readonly_image=false,writeonly_image=false;
    std::string binding,set="0",format;
    for(size_t j=start;j<i;j++) {
      readonly_image|=ts[j].text=="readonly";writeonly_image|=ts[j].text=="writeonly";
      if(j+2<i && ts[j+1].text=="=") {
        if(ts[j].text=="binding")binding=ts[j+2].text;
        if(ts[j].text=="set")set=ts[j+2].text;
      }
      if(ts[j].text=="r32f" || ts[j].text=="r32ui" || ts[j].text=="r32i" ||
         ts[j].text=="rgba16f" || ts[j].text=="rgba32f") format=ts[j].text;
    }
    const auto &name=ts[i].text;
    const bool portable_output=name=="direct_radiance_3_img" ||
      name=="indirect_radiance_3_img" || name=="rp_value_img";
    const bool needs_readwrite=!readonly_image && !writeonly_image &&
      (format=="rgba16f" || format=="rgba32f");
    if(!needs_readwrite && !portable_output)continue;
    if(binding.empty() || format.empty())throw std::runtime_error("Unsupported buffered image: "+name);
    const bool half=format=="rgba16f",rgba=half || format=="rgba32f";
    const int words=half ? 2 : rgba ? 4 : 1;
    const std::string coord=is2d ? "ivec2" : "ivec3";
    const std::string value=format=="r32ui" ? "uvec4" : format=="r32i" ? "ivec4" : "vec4";
    const std::string prefix="wgpu_bi_"+name,meta=prefix+"_meta",data=prefix+"_data";
    std::string out="layout(set="+set+",binding="+binding+",std430) buffer _wgpu_atomic_image_"+name+
      " { uvec4 "+meta+"; uint "+data+"[]; };\n";
    out+="uint "+prefix+"_index("+coord+" p) { ivec3 q="+(is2d ? "ivec3(p,0)" : "p")+
      "; if(any(lessThan(q,ivec3(0))) || any(greaterThanEqual(uvec3(q),"+meta+
      ".xyz))) return 0xffffffffu; return (uint(q.z)*"+meta+".y+uint(q.y))*"+meta+
      ".w+uint(q.x)*"+std::to_string(words)+"u; }\n";
    out+=coord+" "+prefix+"_imageSize() { return "+coord+"("+meta+(is2d ? ".xy" : ".xyz")+"); }\n";
    std::string load;
    if(half)load="vec4(unpackHalf2x16("+data+"[i]),unpackHalf2x16("+data+"[i+1u]))";
    else if(rgba)load="uintBitsToFloat(uvec4("+data+"[i],"+data+"[i+1u],"+data+"[i+2u],"+data+"[i+3u]))";
    else load=value+"("+(format=="r32f" ? "uintBitsToFloat("+data+"[i])" : data+"[i]")+",0,0,1)";
    out+=value+" "+prefix+"_imageLoad("+coord+" p) { uint i="+prefix+"_index(p); if(i==0xffffffffu) return "+value+"(0); return "+load+"; }\n";
    std::string store;
    if(half)store=data+"[i]=packHalf2x16(v.xy); "+data+"[i+1u]=packHalf2x16(v.zw);";
    else if(rgba)store="uvec4 bits=floatBitsToUint(v); "+data+"[i]=bits.x; "+data+"[i+1u]=bits.y; "+data+"[i+2u]=bits.z; "+data+"[i+3u]=bits.w;";
    else store=data+"[i]="+(format=="r32f" ? "floatBitsToUint(v.x)" : "uint(v.x)")+";";
    out+="void "+prefix+"_imageStore("+coord+" p,"+value+" v) { uint i="+prefix+"_index(p); if(i!=0xffffffffu) { "+store+" } }\n";
    edits.push_back({ts[start].begin,ts[i+1].end,out});names.insert(name);
  }
  for(size_t i=0;i+3<ts.size();i++) {
    const auto &op=ts[i].text;
    if((op!="imageLoad" && op!="imageStore" && op!="imageSize") || ts[i+1].text!="(" ||
       !names.count(ts[i+2].text) || (ts[i+3].text!="," && ts[i+3].text!=")"))continue;
    edits.push_back({ts[i].begin,ts[i+3].end,"wgpu_bi_"+ts[i+2].text+"_"+op+(ts[i+3].text==")" ? "()" : "(")});
  }
  std::sort(edits.begin(),edits.end(),[](const Edit &a,const Edit &b){return a.begin>b.begin;});
  std::string result=source;
  for(const auto &edit:edits)result.replace(edit.begin,edit.end-edit.begin,edit.text);
  return result;
}
}
