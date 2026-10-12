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

viewport.addEventListener('pointerdown', () => {
  viewport.focus();
  if (!mode) byId('operation').textContent = 'Keyboard ready · G move / R rotate / S scale';
});
viewport.addEventListener('keydown', event => {
  if (!engine || event.metaKey || event.ctrlKey || event.altKey) return;
  const key = event.key.toLowerCase();
  const handled = ['g', 'r', 's', 'x', 'y', 'z', 'arrowleft', 'arrowright', 'arrowup', 'arrowdown', 'enter', 'escape'];
  if (!handled.includes(key)) return;
  event.preventDefault();
  if (key in modeNames) {
    if (mode) pose = clonePose(savedPose);
    savedPose = clonePose(pose); mode = key; axis = 0;
  } else if (mode && 'xyz'.includes(key) && key.length === 1) {
    axis = 'xyz'.indexOf(key);
  } else if (mode && key.startsWith('arrow')) {
    const direction = (key === 'arrowright' || key === 'arrowup') ? 1 : -1;
    const step = (mode === 'r' ? Math.PI / 36 : 0.1) * (event.shiftKey ? 0.1 : 1);
    const values = pose[poseKeys[mode]];
    values[axis] += direction * step;
    if (mode === 's') values[axis] = Math.max(0.01, values[axis]);
  } else if (mode && key === 'escape') {
    pose = clonePose(savedPose); mode = null;
  } else if (mode && key === 'enter') {
    mode = null;
  }
  byId('operation').textContent = mode ? `${modeNames[mode]} · ${'XYZ'[axis]} axis · arrows adjust · Enter confirms · Esc cancels` : 'Transform confirmed · G / R / S to start again';
  draw();
});
byId('reset').addEventListener('click', () => {
  pose = defaultPose(); mode = null;
  byId('operation').textContent = 'Transform reset · click the viewport to use your keyboard';
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
  window.portBoot?.complete();
  draw();
  prepareOffline();
} catch (error) {
  byId('engine-status').textContent = 'Blender math failed to load';
  byId('checks').textContent = error.message;
  byId('offline-status').textContent = 'Unavailable until the math build loads';
  window.portBoot?.complete();
}
