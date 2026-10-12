// SPDX-License-Identifier: GPL-2.0-or-later
import { loadMath, result, checkMath } from './math-runtime.js';
if (window.portBoot) window.portBoot.started = true;

const byId = id => document.getElementById(id);
const viewport = byId('viewport');
const canvas = byId('canvas');
const context = canvas.getContext('2d');
const defaultPose = () => ({ location: [0, 0, 0], rotation: [0, 0, 0], scale: [1, 1, 1] });
let pose = defaultPose(), savedPose, mode, axis = 0, engine;
const clonePose = value => JSON.parse(JSON.stringify(value));
const modeNames = { g: 'Move', r: 'Rotate', s: 'Scale' };
const poseKeys = { g: 'location', r: 'rotation', s: 'scale' };
const vertices = Array.from({ length: 8 }, (_, index) => [0, 1, 2].map(a => (index & (1 << a)) ? 1 : -1));
const edges = vertices.flatMap((_, i) => [0, 1, 2].filter(a => i < (i ^ (1 << a))).map(a => [i, i ^ (1 << a)]));

function draw() {
  const box = canvas.getBoundingClientRect();
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.round(box.width * dpr);
  canvas.height = Math.round(box.height * dpr);
  context.setTransform(dpr, 0, 0, dpr, 0, 0);
  const width = box.width, height = box.height;
  context.clearRect(0, 0, width, height);
  const project = ([x, y, z]) => {
    const cx = x * 0.866 - y * 0.5, depth = x * 0.5 + y * 0.866;
    const factor = Math.min(width, height) * 0.135;
    return [width / 2 + cx * factor, height / 2 + (depth * 0.45 - z * 0.89) * factor];
  };
  const line = (a, b, color, lineWidth = 1) => {
    context.beginPath(); context.moveTo(...a); context.lineTo(...b);
    context.strokeStyle = color; context.lineWidth = lineWidth; context.stroke();
  };
  for (let i = -8; i <= 8; i++) {
    line(project([i, -8, 0]), project([i, 8, 0]), i === 0 ? '#4f634b' : '#34373c');
    line(project([-8, i, 0]), project([8, i, 0]), i === 0 ? '#64494b' : '#34373c');
  }
  if (!engine) return;
  const transformed = vertices.map(point => {
    engine.bp_transform(...point, ...pose.location, ...pose.rotation, ...pose.scale);
    return project(result(engine));
  });
  for (const [a, b] of edges) line(transformed[a], transformed[b], '#e99b61', 1.75);
  for (const point of transformed) {
    context.fillStyle = '#f2bb91'; context.beginPath(); context.arc(...point, 2.4, 0, Math.PI * 2); context.fill();
  }
  const values = byId('transform-values');
  values.replaceChildren();
  for (const key of ['location', 'rotation', 'scale']) {
    const row = document.createElement('div'); row.className = 'transform-row';
    row.textContent = key.charAt(0).toUpperCase() + key.slice(1);
    const coords = document.createElement('div'); coords.className = 'coordinates';
    pose[key].forEach((value, i) => {
      const item = document.createElement('span');
      item.dataset.field = `${key}-${i}`;
      item.textContent = `${'XYZ'[i]} ${(key === 'rotation' ? value * 180 / Math.PI : value).toFixed(2)}${key === 'rotation' ? '°' : ''}`;
      coords.append(item);
    });
    row.append(coords); values.append(row);
  }
}

const controls = [...document.querySelectorAll('[data-command]')];
const adjustments = new Set(['arrowleft', 'arrowright', 'enter', 'escape']);
function updateControls(message) {
  for (const button of controls) {
    const command = button.dataset.command;
    button.disabled = !engine || (adjustments.has(command) && !mode);
    if (command in modeNames) button.setAttribute('aria-pressed', String(command === mode));
    if ('xyz'.includes(command)) button.setAttribute('aria-pressed', String(command === 'xyz'[axis]));
  }
  byId('operation').textContent = mode
    ? `${modeNames[mode]} · ${'XYZ'[axis]} axis · drag or use − / + · Confirm / Cancel`
    : message || `Drag to move along ${'XYZ'[axis]}, or choose Move / Rotate / Scale`;
}
function adjust(amount) {
  const values = pose[poseKeys[mode]];
  values[axis] += amount;
  if (mode === 's') values[axis] = Math.max(0.01, values[axis]);
}
function command(key, fine = false) {
  if (!engine) return;
  let message;
  if (key in modeNames) {
    if (mode !== key) {
      if (mode) pose = clonePose(savedPose);
      savedPose = clonePose(pose); mode = key;
    }
  } else if (key.length === 1 && 'xyz'.includes(key)) {
    axis = 'xyz'.indexOf(key);
  } else if (mode && key.startsWith('arrow')) {
    const direction = (key === 'arrowright' || key === 'arrowup') ? 1 : -1;
    adjust(direction * (mode === 'r' ? Math.PI / 36 : 0.1) * (fine ? 0.1 : 1));
  } else if (mode && key === 'escape') {
    pose = clonePose(savedPose); mode = null; message = 'Transform cancelled';
  } else if (mode && key === 'enter') {
    mode = null; message = 'Transform confirmed';
  }
  updateControls(message);
  draw();
}
viewport.addEventListener('pointerdown', event => {
  if (!event.target.closest('button')) viewport.focus({ preventScroll: true });
});
viewport.addEventListener('contextmenu', event => event.preventDefault());
viewport.addEventListener('selectstart', event => event.preventDefault());
viewport.addEventListener('keydown', event => {
  if (!engine || event.metaKey || event.ctrlKey || event.altKey) return;
  const key = event.key.toLowerCase();
  if (event.target.closest('button') && key === 'enter') return;
  if (!['g', 'r', 's', 'x', 'y', 'z', 'arrowleft', 'arrowright', 'arrowup', 'arrowdown', 'enter', 'escape'].includes(key)) return;
  event.preventDefault();
  command(key, event.shiftKey);
});
for (const button of controls) {
  button.addEventListener('click', () => {
    command(button.dataset.command);
    viewport.focus({ preventScroll: true });
  });
}
let drag;
canvas.addEventListener('pointerdown', event => {
  if (!engine || !event.isPrimary || event.button !== 0) return;
  event.preventDefault();
  canvas.setPointerCapture(event.pointerId);
  drag = { id: event.pointerId, x: event.clientX, y: event.clientY,
           initialX: event.clientX, initialY: event.clientY, moved: false, implicit: !mode };
});
canvas.addEventListener('pointermove', event => {
  if (!drag || drag.id !== event.pointerId) return;
  event.preventDefault();
  if (!drag.moved) {
    if (Math.hypot(event.clientX - drag.initialX, event.clientY - drag.initialY) < 5) return;
    if (!mode) command('g');
    drag.moved = true;
  }
  const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
  drag.x = event.clientX; drag.y = event.clientY;
  if (!mode) return;
  if (mode === 'r') adjust((dx - dy) * Math.PI / 360);
  else if (mode === 's') adjust((dx - dy) * 0.01);
  else {
    const [ux, uy] = [[0.866, 0.225], [-0.5, 0.866 * 0.45], [0, -0.89]][axis];
    const box = canvas.getBoundingClientRect();
    adjust((dx * ux + dy * uy) / (Math.min(box.width, box.height) * 0.135 * (ux * ux + uy * uy)));
  }
  updateControls(); draw();
});
function endDrag(event, cancelled) {
  if (!drag || drag.id !== event.pointerId) return;
  const pending = drag;
  drag = null;
  if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
  if (pending.moved && mode) {
    if (cancelled) command('escape');
    else if (pending.implicit) command('enter');
  }
}
canvas.addEventListener('pointerup', event => endDrag(event, false));
canvas.addEventListener('pointercancel', event => endDrag(event, true));
canvas.addEventListener('lostpointercapture', event => endDrag(event, true));
byId('reset').addEventListener('click', () => {
  pose = defaultPose(); mode = null; axis = 0;
  updateControls('Transform reset · drag or choose a transform');
  draw();
});
if (typeof ResizeObserver !== 'undefined') new ResizeObserver(draw).observe(canvas);
else window.addEventListener('resize', draw);

async function capabilities() {
  let gpu = 'Unavailable';
  try {
    if (navigator.gpu) gpu = await navigator.gpu.requestAdapter() ? 'Available' : 'No adapter';
  } catch { gpu = 'Unavailable'; }
  const entries = [
    ['WebAssembly', typeof WebAssembly === 'object' ? 'Available' : 'Unavailable'],
    ['WebGPU adapter', gpu],
    ['Shared memory', window.crossOriginIsolated === true && typeof SharedArrayBuffer !== 'undefined' ? 'Available' : 'Unavailable'],
    ['App mode', matchMedia('(display-mode: standalone)').matches || navigator.standalone ? 'Installed' : 'Browser'],
  ];
  const list = byId('capabilities'); list.replaceChildren();
  for (const [name, state] of entries) {
    const dt = document.createElement('dt'), dd = document.createElement('dd');
    dt.textContent = name; dd.textContent = state; list.append(dt, dd);
  }
}

async function prepareOffline() {
  const status = byId('offline-status');
  if (window.isSecureContext !== true || !('serviceWorker' in navigator)) {
    status.textContent = 'Local server mode · keep WorldWideWeb running'; return;
  }
  try {
    const registration = await navigator.serviceWorker.register('./sw.js');
    const ready = await Promise.race([
      navigator.serviceWorker.ready,
      new Promise((_, reject) => setTimeout(() => reject(new Error('Offline setup timed out; retry while connected')), 15000)),
    ]);
    const channel = new MessageChannel();
    const response = await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('Offline cache check timed out')), 5000);
      channel.port1.onmessage = event => { clearTimeout(timeout); resolve(event.data); };
      (ready.active || registration.active).postMessage('check-offline', [channel.port2]);
    });
    status.textContent = response.complete ? 'Downloaded · ready for offline reload' : 'Download incomplete · reconnect and reload';
  } catch (error) { status.textContent = `Not ready: ${error.message}`; }
}

capabilities();
try {
  const response = await fetch('./engine/blender-math.wasm');
  if (!response.ok) throw new Error(`Math build unavailable (HTTP ${response.status})`);
  engine = await loadMath(await response.arrayBuffer());
  const count = checkMath(engine);
  byId('engine-status').textContent = 'Blender math running locally';
  byId('engine-dot').classList.add('ready');
  byId('checks').textContent = `${count} source checks passed · Blender 5.2.2`;
  byId('reset').disabled = false;
  updateControls();
  window.portBoot?.complete();
  draw();
  prepareOffline();
} catch (error) {
  byId('engine-status').textContent = 'Blender math failed to load';
  byId('checks').textContent = error.message;
  byId('offline-status').textContent = 'Unavailable until the math build loads';
  window.portBoot?.complete();
}
