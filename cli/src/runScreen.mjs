// One interactive list screen. Plain async function — no component tree.
// Action/Back rows return a token directly (ending the loop); Toggle/
// Picker/Text/Number rows mutate config via item.setValue() and redraw in
// place. Owns an inline text-edit sub-mode for Text/Number rows.

import { nextKeyBatch, isExitCombo, clearScreen } from './term.mjs';
import { buildHeader, buildFooter, buildRow, buildEditBox } from './render.mjs';
import { styles } from './theme.mjs';

function firstSelectable(items) {
  const i = items.findIndex((it) => it.kind !== 'separator');
  return i === -1 ? 0 : i;
}

function nextSelectable(items, current, direction) {
  const n = items.length;
  let idx = (((current + direction) % n) + n) % n;
  for (let i = 0; i < n; i++) {
    if (items[idx].kind !== 'separator') return idx;
    idx = (((idx + direction) % n) + n) % n;
  }
  return current;
}

export async function runScreen({ title, breadcrumb = [], summary = '', items }) {
  let focused = firstSelectable(items);
  let editing = false;
  let editBuffer = [];
  let editCursor = 0;

  function draw() {
    clearScreen();
    const lines = [buildHeader({ breadcrumb, summary }), '', styles.accentBold.render(title), ''];
    for (let i = 0; i < items.length; i++) {
      lines.push('  ' + buildRow(items[i], i === focused && !editing));
    }
    if (editing) {
      lines.push('', buildEditBox(items[focused].label, editBuffer.join(''), editCursor, items[focused].secret));
    }
    lines.push(
      '',
      buildFooter(editing ? ['Enter confirm', 'Esc cancel'] : ['↑↓ Navigate', 'Enter Select', '←→ Adjust', 'Esc Back']),
    );
    process.stdout.write(lines.join('\n') + '\n');
  }

  async function cyclePicker(item, direction) {
    const idx = item.options.findIndex(([v]) => v === item.getValue());
    const n = item.options.length;
    const next = (((idx + direction) % n) + n) % n;
    await item.setValue(item.options[next][0]);
  }

  async function nudgeNumber(item, direction) {
    const raw = Number(item.getValue()) + direction * item.step;
    const val = item.isFloat ? Math.round(Math.max(item.minVal, raw) * 10) / 10 : Math.max(item.minVal, Math.round(raw));
    await item.setValue(val);
  }

  async function submitEdit() {
    const item = items[focused];
    const value = editBuffer.join('');
    editing = false;
    // Secret fields render blank while editing — an empty submit means
    // "left it untouched," not "clear the key."
    if (item.secret && value === '') return;
    if (item.kind === 'number') {
      const num = Number(value);
      if (Number.isNaN(num)) return;
      const val = item.isFloat ? Math.round(Math.max(item.minVal, num) * 10) / 10 : Math.max(item.minVal, Math.round(num));
      await item.setValue(val);
    } else {
      await item.setValue(value);
    }
  }

  // Applies one keypress's effect on state. Returns a token/'back' if the
  // screen should end, otherwise undefined. No drawing here — the caller
  // draws once after a whole batch of keys has been applied (see below).
  async function handleKey(key) {
    if (isExitCombo(key)) {
      clearScreen();
      process.exit(0);
    }

    if (editing) {
      if (key.name === 'return') {
        await submitEdit();
      } else if (key.name === 'escape') {
        editing = false;
      } else if (key.name === 'backspace') {
        if (editCursor > 0) {
          editBuffer.splice(editCursor - 1, 1);
          editCursor--;
        }
      } else if (key.name === 'delete') {
        if (editCursor < editBuffer.length) editBuffer.splice(editCursor, 1);
      } else if (key.name === 'left') {
        editCursor = Math.max(0, editCursor - 1);
      } else if (key.name === 'right') {
        editCursor = Math.min(editBuffer.length, editCursor + 1);
      } else if (key.name === 'home') {
        editCursor = 0;
      } else if (key.name === 'end') {
        editCursor = editBuffer.length;
      } else if (key.sequence && !key.ctrl && !key.meta && key.sequence.length === 1) {
        const code = key.sequence.codePointAt(0);
        if (code >= 32 && code !== 127) {
          editBuffer.splice(editCursor, 0, key.sequence);
          editCursor++;
        }
      }
      return undefined;
    }

    if (key.name === 'up') {
      focused = nextSelectable(items, focused, -1);
    } else if (key.name === 'down') {
      focused = nextSelectable(items, focused, 1);
    } else if (key.name === 'escape' || key.sequence === 'q') {
      return 'back';
    } else if (key.name === 'return') {
      const item = items[focused];
      if (item.kind === 'action') return item.token;
      if (item.kind === 'back') return 'back';
      if (item.kind === 'toggle') await item.setValue(!item.getValue());
      else if (item.kind === 'picker') await cyclePicker(item, 1);
      else if (item.kind === 'text' || item.kind === 'number') {
        editBuffer = item.secret ? [] : Array.from(String(item.getValue() ?? ''));
        editCursor = editBuffer.length;
        editing = true;
      }
    } else if (key.sequence === ' ') {
      const item = items[focused];
      if (item.kind === 'toggle') await item.setValue(!item.getValue());
      else if (item.kind === 'picker') await cyclePicker(item, 1);
    } else if (key.name === 'left') {
      const item = items[focused];
      if (item.kind === 'picker') await cyclePicker(item, -1);
      else if (item.kind === 'number') await nudgeNumber(item, -1);
    } else if (key.name === 'right') {
      const item = items[focused];
      if (item.kind === 'picker') await cyclePicker(item, 1);
      else if (item.kind === 'number') await nudgeNumber(item, 1);
    }
    return undefined;
  }

  draw();
  while (true) {
    // Apply a whole burst of queued keys (arrow-key auto-repeat, a fast
    // double-tap) before redrawing once — see nextKeyBatch()'s comment for
    // why firing one redraw per key in a tight burst is unsafe here.
    const keys = await nextKeyBatch();
    let result;
    for (const key of keys) {
      result = await handleKey(key);
      if (result !== undefined) break;
    }
    if (result !== undefined) return result;
    draw();
  }
}
