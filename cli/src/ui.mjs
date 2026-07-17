// Low-level rendering + raw-mode input primitives. Zero dependencies —
// styling via Node's built-in util.styleText, box-drawing via plain
// Unicode/ANSI, mirrors the visual language of tui.py's curses screens
// (same border characters, same color roles) without needing curses/blessed/
// Ink for what is fundamentally a simple redraw-on-keypress loop.

import { styleText } from 'node:util';
import readline from 'node:readline';

const ANSI_RE = /\x1b\[[0-9;]*m/g;

export function vlen(text) {
  return text.replace(ANSI_RE, '').length;
}

export function paint(text, ...styles) {
  return styles.length ? styleText(styles, text) : text;
}

export function clearScreen() {
  process.stdout.write('\x1b[2J\x1b[H');
}

function hideCursor() { process.stdout.write('\x1b[?25l'); }
function showCursor() { process.stdout.write('\x1b[?25h'); }

export function screenSize() {
  return {
    cols: process.stdout.columns || 80,
    rows: process.stdout.rows || 24,
  };
}

// ── Raw-mode keypress capture ──────────────────────────────────────────

let rawEnabled = false;
let pendingResolvers = [];

function onKeypress(str, key) {
  const resolve = pendingResolvers.shift();
  if (resolve) resolve(key || { name: str, sequence: str });
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
  return new Promise((resolve) => pendingResolvers.push(resolve));
}

export function isExitCombo(key) {
  return Boolean(key.ctrl && key.name === 'c');
}

// ── Banner ──────────────────────────────────────────────────────────────

const BANNER_WIDTH = 60;

function bannerRow(text) {
  const bar = paint('║', 'cyan');
  const pad = Math.max(0, BANNER_WIDTH - 2 - vlen(text));
  return `${bar} ${text}${' '.repeat(pad)} ${bar}`;
}

function bannerBorder(left, right) {
  return paint(left + '═'.repeat(BANNER_WIDTH) + right, 'cyan');
}

export function renderBanner({ cfg, providerLabel, currentModel }) {
  const lines = [
    bannerBorder('╔', '╗'),
    bannerRow(paint('  Anki Vocabulary Deck Generator  v2.0  ', 'bold', 'cyan')),
    bannerBorder('╠', '╣'),
    bannerRow(paint(`  Language : ${String(cfg.SOURCE_LANG || '').toUpperCase()} -> ${cfg.TARGET_LANG || ''}`, 'yellow')),
    bannerRow(paint(`  Template : ${cfg.CARD_TEMPLATE}   |   Card type : ${cfg.CARD_TYPE}`, 'dim')),
    bannerRow(paint(`  AI provider : ${providerLabel}   |   Model : ${currentModel}`, 'dim')),
    bannerBorder('╚', '╝'),
  ];
  return lines.join('\n');
}

// ── Inline text editor (used by TextInput / NumberInput) ───────────────

export async function editString(label, initial = '', secret = false) {
  const { cols, rows } = screenSize();
  const iw = Math.max(24, cols - 6);
  const boxY = Math.max(1, rows - 6);
  let buf = Array.from(initial);
  let cpos = buf.length;

  function draw() {
    for (let i = 0; i < 5; i++) {
      process.stdout.write(`\x1b[${boxY + i};1H\x1b[2K`);
    }
    process.stdout.write(`\x1b[${boxY};1H`);
    const border = '═'.repeat(iw);
    process.stdout.write(paint(' ╔' + border + '╗', 'cyan') + '\n');
    const prompt = `  ${label}:`;
    process.stdout.write(
      paint(' ║', 'cyan') + paint(prompt.slice(0, iw).padEnd(iw), 'bold', 'cyan') + paint('║', 'cyan') + '\n',
    );
    const text = buf.join('');
    const display = secret ? '*'.repeat(text.length) : text;
    const fieldW = iw - 2;
    const start = Math.max(0, cpos - fieldW + 1);
    const visible = display.slice(start, start + fieldW);
    process.stdout.write(
      paint(' ║', 'cyan') + ' ' + paint(visible.padEnd(fieldW), 'yellow', 'underline') + ' ' + paint('║', 'cyan') + '\n',
    );
    const hint = '  Enter = confirm   Esc = cancel';
    process.stdout.write(
      paint(' ║', 'cyan') + paint(hint.slice(0, iw).padEnd(iw), 'dim') + paint('║', 'cyan') + '\n',
    );
    process.stdout.write(paint(' ╚' + border + '╝', 'cyan') + '\n');
    const cursorX = 4 + (cpos - start);
    process.stdout.write(`\x1b[${boxY + 2};${cursorX}H`);
  }

  draw();
  let result = null;
  while (true) {
    const key = await nextKey();
    if (isExitCombo(key)) { result = null; break; }
    if (key.name === 'return') { result = buf.join(''); break; }
    if (key.name === 'escape') { result = null; break; }
    else if (key.name === 'backspace') { if (cpos > 0) { buf.splice(cpos - 1, 1); cpos--; } }
    else if (key.name === 'delete') { if (cpos < buf.length) buf.splice(cpos, 1); }
    else if (key.name === 'left') cpos = Math.max(0, cpos - 1);
    else if (key.name === 'right') cpos = Math.min(buf.length, cpos + 1);
    else if (key.name === 'home') cpos = 0;
    else if (key.name === 'end') cpos = buf.length;
    else if (key.sequence && !key.ctrl && !key.meta && key.sequence.length === 1) {
      const code = key.sequence.codePointAt(0);
      if (code >= 32 && code < 127) { buf.splice(cpos, 0, key.sequence); cpos++; }
    }
    draw();
  }
  return result;
}

// ── Core menu loop ───────────────────────────────────────────────────────

function firstSelectable(items) {
  const i = items.findIndex((it) => it.selectable !== false);
  return i === -1 ? 0 : i;
}

function nextSelectable(items, current, direction) {
  const n = items.length;
  let idx = ((current + direction) % n + n) % n;
  for (let i = 0; i < n; i++) {
    if (items[idx].selectable !== false) return idx;
    idx = ((idx + direction) % n + n) % n;
  }
  return current;
}

const STATUS_HINT = '  ↑↓ navigate   ←→ change value   Enter select   Esc / q  back  ';

/**
 * Arrow-key driven menu. `items` implement { selectable, render(width, focused),
 * onEnter, onLeft, onRight } — same contract as tui.py's MenuItem subclasses.
 * `getBanner()` returns cached banner data (no subprocess spawn per frame).
 */
export async function runMenu(title, items, getBanner) {
  let current = firstSelectable(items);

  while (true) {
    const { cols, rows } = screenSize();
    clearScreen();
    process.stdout.write(renderBanner(getBanner()) + '\n\n');
    process.stdout.write(paint(`  ${title}`, 'bold', 'cyan') + '\n');
    process.stdout.write(paint('  ' + '─'.repeat(Math.max(0, cols - 4)), 'dim') + '\n\n');

    const availWidth = Math.max(20, cols - 4);
    const visibleCount = Math.max(1, rows - 13);
    const scrollStart = Math.max(0, current - visibleCount + 1);
    const visible = items.slice(scrollStart, scrollStart + visibleCount);

    visible.forEach((item, i) => {
      const idx = scrollStart + i;
      const focused = idx === current;
      process.stdout.write('  ' + item.render(availWidth, focused) + '\n');
    });

    process.stdout.write('\n' + paint(STATUS_HINT.padEnd(cols - 1), 'black', 'bgCyan') + '\n');

    const key = await nextKey();
    if (isExitCombo(key)) {
      disableRawMode();
      process.exit(0);
    } else if (key.name === 'up') {
      current = nextSelectable(items, current, -1);
    } else if (key.name === 'down') {
      current = nextSelectable(items, current, 1);
    } else if (key.name === 'return') {
      const result = await items[current].onEnter?.();
      if (result === 'back') break;
    } else if (key.name === 'left') {
      await items[current].onLeft?.();
    } else if (key.name === 'right') {
      await items[current].onRight?.();
    } else if (key.name === 'space') {
      const item = items[current];
      if (item.respondsToSpace) await item.onEnter?.();
    } else if (key.name === 'escape' || key.sequence === 'q') {
      break;
    }
  }
}
