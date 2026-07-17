#!/usr/bin/env node
// Entry point for the JS TUI. Pure frontend over main.py — see cli/src/bridge.mjs.

import { enableRawMode, disableRawMode, clearScreen } from './ui.mjs';
import { mainMenu } from './screens.mjs';

if (!process.stdin.isTTY) {
  console.error('This interactive menu needs a real terminal (stdin is not a TTY).');
  console.error('Run it directly in your terminal: node cli/src/index.mjs');
  process.exit(1);
}

try {
  enableRawMode();
  await mainMenu();
} catch (err) {
  disableRawMode();
  console.error('\n[ERROR]', err.message || err);
  process.exit(1);
}

disableRawMode();
clearScreen();
process.exit(0);
