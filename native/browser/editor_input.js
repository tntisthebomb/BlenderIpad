// Forward committed browser text to Blender while retaining its active field.
// A visible textarea lets Safari present the iPad keyboard and compose Unicode.
(() => {
  const canvas=document.getElementById('canvas');
  const header=document.querySelector('header');
  if (!canvas || !header) return;
  const button=document.createElement('button');
  button.type='button';button.id='tablet-keyboard';button.textContent='Keyboard';
  button.setAttribute('aria-expanded','false');
  header.insertBefore(button,document.getElementById('device-report'));
  const panel=document.createElement('aside');
  panel.id='tablet-input-panel';panel.hidden=true;
  panel.setAttribute('aria-label','Blender keyboard');
  panel.innerHTML='<label for="tablet-text">Type into the active Blender field</label>'+
    '<textarea id="tablet-text" rows="1" autocomplete="off" autocapitalize="off" spellcheck="false" aria-label="Text for Blender"></textarea>'+
    '<div id="tablet-keys"></div>';
  document.body.append(panel);
  const style=document.createElement('style');
  style.textContent=`#tablet-input-panel{position:fixed;z-index:5;top:44px;right:8px;
    width:min(510px,90vw);box-sizing:border-box;padding:10px;background:#303030;
    border:1px solid #777;border-radius:6px;box-shadow:0 4px 18px #0008}
    #tablet-input-panel[hidden]{display:none}
    #tablet-input-panel label{display:block;font:13px system-ui;margin-bottom:6px}
    #tablet-text{box-sizing:border-box;width:100%;min-height:44px;font:16px system-ui;
      background:#202020;color:#eee;border:1px solid #888;resize:none}
    #tablet-keys{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
    #tablet-keys button{min-height:40px;min-width:42px}
    #tablet-keys button[aria-pressed=true]{background:#3676ac}`;
  document.head.append(style);
  const input=panel.querySelector('textarea');
  const sentinel='\ufeff';
  const modifiers={ctrlKey:false,shiftKey:false,altKey:false};
  let transferringFocus=false,composing=false;
  const punctuation={' ':'Space','.':'Period',',':'Comma','-':'Minus','=':'Equal',
    '/':'Slash',';':'Semicolon',"'":'Quote','[':'BracketLeft',']':'BracketRight',
    '`':'Backquote','\\':'Backslash'};
  const codeFor=key=>/^[a-z]$/i.test(key)?'Key'+key.toUpperCase():
    /^[0-9]$/.test(key)?'Digit'+key:punctuation[key] || 'KeyA';
  const emit=(type,key,code,flags)=>canvas.dispatchEvent(new KeyboardEvent(type,
    {key,code,bubbles:true,cancelable:true,...flags}));
  function sendKey(key,code,physical={}) {
    if (!window.blenderEditor || document.body.dataset.error) return;
    const flags={metaKey:!!physical.metaKey};
    for (const name of Object.keys(modifiers)) flags[name]=modifiers[name] || !!physical[name];
    const held=[];
    for (const [flag,keyName,keyCode] of [['ctrlKey','Control','ControlLeft'],
      ['shiftKey','Shift','ShiftLeft'],['altKey','Alt','AltLeft'],['metaKey','Meta','MetaLeft']]) {
      if (flags[flag]) {emit('keydown',keyName,keyCode,flags);held.push([keyName,keyCode]);}
    }
    emit('keydown',key,code,flags);emit('keyup',key,code,flags);
    for (const [keyName,keyCode] of held.reverse()) emit('keyup',keyName,keyCode,{});
  }
  function sendText(text) {
    for (let character of text) {
      if (character==='\r') continue;
      if (character==='\n') sendKey('Enter','Enter');
      else if (character==='\t') sendKey('Tab','Tab');
      else {
        if (modifiers.shiftKey && /^[a-z]$/.test(character)) character=character.toUpperCase();
        sendKey(character,codeFor(character));
      }
    }
  }
  function reset() {input.value=sentinel;input.setSelectionRange(1,1);}
  function flushText() {
    if (composing) return;
    const text=input.value.startsWith(sentinel)?input.value.slice(1):input.value;
    reset();if (text) sendText(text);
  }
  // Canvas blur normally deactivates Blender and commits its text field. Skip
  // that one event while transferring DOM focus to Safari's keyboard control.
  canvas.addEventListener('blur',event=>{
    if (transferringFocus) event.stopImmediatePropagation();
  },true);
  function focusInput() {
    transferringFocus=true;
    try {input.focus({preventScroll:true});} finally {transferringFocus=false;}
  }
  function close() {
    flushText();panel.hidden=true;button.setAttribute('aria-expanded','false');
    canvas.focus({preventScroll:true});
  }
  button.addEventListener('pointerdown',event=>event.preventDefault());
  button.addEventListener('mousedown',event=>event.preventDefault());
  button.addEventListener('click',()=>{
    if (!panel.hidden) {close();return;}
    reset();panel.hidden=false;button.setAttribute('aria-expanded','true');focusInput();
  });
  input.addEventListener('compositionstart',()=>{composing=true;});
  input.addEventListener('compositionend',()=>{composing=false;setTimeout(flushText,0);});
  input.addEventListener('input',event=>{
    if (composing || event.isComposing) return;
    if ((event.inputType || '').startsWith('delete')) {
      sendKey(event.inputType.endsWith('Forward')?'Delete':'Backspace',
              event.inputType.endsWith('Forward')?'Delete':'Backspace');reset();
    } else flushText();
  });
  input.addEventListener('keydown',event=>{
    if (event.isComposing || composing) return;
    const special=['Enter','Escape','Tab','Backspace','Delete','ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End'];
    if (special.includes(event.key) || ((event.ctrlKey || event.metaKey) && event.key.length===1)) {
      event.preventDefault();sendKey(event.key,event.code || event.key,event);
    }
  });
  const keys=panel.querySelector('#tablet-keys');
  for (const [label,key,code] of [['Esc','Escape','Escape'],['Tab','Tab','Tab'],
    ['Enter','Enter','Enter'],['⌫','Backspace','Backspace'],['←','ArrowLeft','ArrowLeft'],['→','ArrowRight','ArrowRight']]) {
    const control=document.createElement('button');control.type='button';control.textContent=label;
    control.addEventListener('pointerdown',event=>event.preventDefault());
    control.addEventListener('mousedown',event=>event.preventDefault());
    control.addEventListener('click',()=>{flushText();sendKey(key,code);focusInput();});keys.append(control);
  }
  for (const [label,flag] of [['Ctrl','ctrlKey'],['Shift','shiftKey'],['Alt','altKey']]) {
    const control=document.createElement('button');control.type='button';control.textContent=label;
    control.setAttribute('aria-pressed','false');
    control.addEventListener('pointerdown',event=>event.preventDefault());
    control.addEventListener('mousedown',event=>event.preventDefault());
    control.addEventListener('click',()=>{modifiers[flag]=!modifiers[flag];
      control.setAttribute('aria-pressed',String(modifiers[flag]));focusInput();});keys.append(control);
  }
  const done=document.createElement('button');done.type='button';done.textContent='Done';
  done.addEventListener('pointerdown',event=>event.preventDefault());
  done.addEventListener('mousedown',event=>event.preventDefault());
  done.addEventListener('click',close);keys.append(done);
  new MutationObserver(()=>{
    if (document.body.dataset.error) {
      panel.hidden=true;button.setAttribute('aria-expanded','false');input.blur();
    }
  }).observe(document.body,{attributes:true,attributeFilter:['data-error']});
})();
