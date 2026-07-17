// Thin subprocess bridge to main.py. All business logic (AI calls, GIF/TTS,
// SQLite, .apkg export, config.py read/write) stays in Python — this module
// never re-implements any of it, only shells out and (de)serializes JSON.

import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const PYTHON_BIN = process.env.PYTHON_BIN || 'python3';

// -B: never read/write __pycache__ .pyc files. config.py is rewritten by
// every --set-config call, sometimes multiple times within the same
// filesystem-mtime tick (e.g. rapid Left/Right presses on a NumberInput);
// since bytecode-cache invalidation is (mtime, size)-based, two writes with
// equal-length values in the same tick can make Python serve a stale cached
// module. -B forces a fresh read+compile from the actual file every time.
function pyArgs(args) {
  return ['-B', 'main.py', ...args];
}

function runJson(flag) {
  const result = spawnSync(PYTHON_BIN, pyArgs([flag]), { cwd: ROOT, encoding: 'utf-8' });
  if (result.error) {
    throw new Error(`Could not launch "${PYTHON_BIN}": ${result.error.message}`);
  }
  if (result.status !== 0) {
    throw new Error(`main.py ${flag} exited ${result.status}\n${result.stderr}`);
  }
  return JSON.parse(result.stdout);
}

function runInherited(args) {
  const result = spawnSync(PYTHON_BIN, pyArgs(args), { cwd: ROOT, stdio: 'inherit' });
  if (result.error) {
    throw new Error(`Could not launch "${PYTHON_BIN}": ${result.error.message}`);
  }
  return result.status;
}

export const bridge = {
  config: () => runJson('--config-json'),
  options: () => runJson('--options-json'),
  stats: () => runJson('--stats-json'),

  setConfig(key, value, type) {
    const result = spawnSync(
      PYTHON_BIN,
      pyArgs([`--set-config=${key}`, `--value=${value}`, `--type=${type}`]),
      { cwd: ROOT, encoding: 'utf-8' },
    );
    if (result.error) {
      throw new Error(`Could not launch "${PYTHON_BIN}": ${result.error.message}`);
    }
    if (result.status !== 0) {
      throw new Error(`main.py --set-config exited ${result.status}\n${result.stderr}`);
    }
    return JSON.parse(result.stdout).ok;
  },

  // Inherits stdio so Python's own colored progress output prints directly
  // into this same terminal (mirrors tui.py's Action(print_mode=True)).
  generate: () => runInherited(['--generate']),
  export: (cardType) => runInherited(cardType ? [`--export=${cardType}`] : ['--export']),
};
