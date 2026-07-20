#!/usr/bin/env node
// Entry point for the JS TUI. Pure frontend over main.py — see cli/src/bridge.mjs.

import { enableRawMode, disableRawMode, clearScreen } from './term.mjs';

if (!process.stdin.isTTY) {
  console.error('This interactive menu needs a real terminal (stdin is not a TTY).');
  console.error('Run it directly in your terminal: node cli/src/index.mjs');
  process.exit(1);
}

// Lip Gloss detects the terminal's color profile once, at import time.
// Konsole (and most modern terminals) support truecolor but don't always
// export COLORTERM to say so — set a conservative default before the first
// module that touches @charmland/lipgloss (screens.mjs, transitively) loads.
process.env.COLORTERM ??= 'truecolor';

const { mainMenu } = await import('./screens.mjs');

enableRawMode();
try {
  await mainMenu();
} catch (err) {
  disableRawMode();
  console.error('\n[ERROR]', err.message || err);
  process.exit(1);
}

disableRawMode();
clearScreen();
process.exit(0);
