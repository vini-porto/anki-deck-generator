// Raw-mode input + low-level terminal primitives. Lip Gloss only builds
// styled strings — it has no input loop or screen model (that's Bubble
// Tea's job in Go) — so this hand-rolled loop owns keypress capture and
// frame redraws, same shape as this project's original zero-dependency
// attempt before Ink was tried.

import readline from 'node:readline';

export function screenSize() {
  return {
    cols: process.stdout.columns || 80,
    rows: process.stdout.rows || 24,
  };
}

export function clearScreen() {
  process.stdout.write('\x1b[2J\x1b[H');
}

function hideCursor() {
  process.stdout.write('\x1b[?25l');
}

function showCursor() {
  process.stdout.write('\x1b[?25h');
}

let rawEnabled = false;
// Two-sided queue: readline can emit several 'keypress' events synchronously
// within one 'data' event (e.g. a fast double-tap, or bracketed paste) —
// all of them fire before the awaited nextKey() continuation gets a chance
// to re-subscribe. Buffer keys that arrive with nobody waiting, so a rapid
// key never gets silently dropped.
let keyQueue = [];
let resolverQueue = [];

function onKeypress(str, key) {
  const k = key || { name: str, sequence: str };
  const resolve = resolverQueue.shift();
  if (resolve) resolve(k);
  else keyQueue.push(k);
}

export function enableRawMode() {
  if (rawEnabled) return;
  readline.emitKeypressEvents(process.stdin);
  if (process.stdin.isTTY) process.stdin.setRawMode(true);
  process.stdin.resume();
  process.stdin.on('keypress', onKeypress);
  hideCursor();
  rawEnabled = true;
}

export function disableRawMode() {
  if (!rawEnabled) return;
  process.stdin.off('keypress', onKeypress);
  if (process.stdin.isTTY) process.stdin.setRawMode(false);
  process.stdin.pause();
  showCursor();
  rawEnabled = false;
}

export function nextKey() {
  if (keyQueue.length) return Promise.resolve(keyQueue.shift());
  return new Promise((resolve) => resolverQueue.push(resolve));
}

// Like nextKey(), but drains every key already buffered (or that arrives
// synchronously alongside the first one) into a single array. A burst of
// held/rapid-fire keys — arrow-key auto-repeat, a fast double-tap — can
// otherwise trigger several full redraws within milliseconds; each redraw
// is ~20 Lip Gloss WASM calls, and firing many redraws back-to-back with no
// yield between them reliably crashed the WASM runtime ("table index out
// of bounds") in testing. Draining a whole burst and redrawing once after
// applying it keeps the WASM call rate sane without dropping any input.
export function nextKeyBatch() {
  if (keyQueue.length) {
    const batch = keyQueue;
    keyQueue = [];
    return Promise.resolve(batch);
  }
  return new Promise((resolve) => {
    resolverQueue.push((key) => {
      const rest = keyQueue;
      keyQueue = [];
      resolve([key, ...rest]);
    });
  });
}

// Discard any keys buffered while raw mode was off (e.g. impatient presses
// during a generate/export subprocess run) — they shouldn't replay as
// phantom navigation once the menu redraws.
export function flushKeys() {
  keyQueue = [];
}

export function isExitCombo(key) {
  return Boolean(key.ctrl && key.name === 'c');
}
