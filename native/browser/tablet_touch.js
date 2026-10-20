// SPDX-License-Identifier: GPL-2.0-or-later
// Wait briefly for a second finger before committing a native selection press.
// A native left-button release cannot undo selection already executed on press.
(()=>{
 'use strict';
 window.installBlenderTabletTouch=(canvas,enabled)=>{
  if(!enabled)return;
  let pending=null,timer=null,replaying=false,forwarded=false,gesture=false;
  const report={version:'tablet-touch-v1',singleGestures:0,multiGestures:0,cancelledSelectionPresses:0};
  window.blenderTabletTouchReport=report;
  function snapshot(event){
   return {type:event.type,touches:Array.from(event.touches),targetTouches:Array.from(event.targetTouches),
    changedTouches:Array.from(event.changedTouches),ctrlKey:event.ctrlKey,shiftKey:event.shiftKey,
    altKey:event.altKey,metaKey:event.metaKey};
  }
  function replay(data,allChanged=false){
   const fields={...data,bubbles:true,cancelable:true,changedTouches:allChanged?data.touches:data.changedTouches};
   let event;
   try{event=new TouchEvent(data.type,fields);}
   catch{
    event=new Event(data.type,{bubbles:true,cancelable:true});
    for(const key of ['touches','targetTouches','changedTouches','ctrlKey','shiftKey','altKey','metaKey']){
     Object.defineProperty(event,key,{value:fields[key]});
    }
   }
   replaying=true;try{canvas.dispatchEvent(event);}finally{replaying=false;}
  }
  function flush(){
   clearTimeout(timer);timer=null;
   if(!pending)return;
   const first=pending;pending=null;forwarded=true;report.singleGestures++;replay(first);
  }
  function intercept(event){
   if(replaying||event.target!==canvas)return;
   if(event.cancelable)event.preventDefault();
   event.stopImmediatePropagation();
   const data=snapshot(event);
   if(event.type==='touchcancel'){
    clearTimeout(timer);timer=null;pending=null;
    if(forwarded||gesture)replay(data);
    forwarded=false;gesture=false;return;
   }
   if(event.type==='touchstart'&&data.touches.length===1&&!forwarded&&!gesture){
    pending=data;timer=setTimeout(flush,90);return;
   }
   if(data.touches.length>=2){
    if(pending){clearTimeout(timer);timer=null;pending=null;report.cancelledSelectionPresses++;}
    if(!gesture){gesture=true;report.multiGestures++;}
    // Include the first finger when its withheld start never reached GHOST.
    replay(data,event.type==='touchstart'&&!forwarded);return;
   }
   if(gesture){
    replay(data);
    if(data.touches.length===0){gesture=false;forwarded=false;}
    return;
   }
   if(pending&&event.type==='touchmove'){flush();replay(data);return;}
   if(event.type==='touchend'){
    flush();if(forwarded)replay(data);forwarded=false;return;
   }
   if(forwarded)replay(data);
  }
  for(const type of ['touchstart','touchmove','touchend','touchcancel']){
   window.addEventListener(type,intercept,{capture:true,passive:false});
  }
  window.addEventListener('pagehide',()=>{clearTimeout(timer);pending=null;});
 };
})();
