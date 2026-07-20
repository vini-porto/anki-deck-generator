// Pure string builders for each part of a frame (header, footer, one row
// per item kind, the inline text-edit box). All styling goes through
// theme.mjs's pre-built Style singletons — see theme.mjs for why these are
// never constructed fresh per redraw. runScreen.mjs/staticScreen.mjs join
// these into one big string and write it in a single pass each redraw.

import { styles, GRADIENT_TITLE } from './theme.mjs';

const CARET = styles.accentBold.render('❯ ');
const CARET_BLANK = '  ';

export function buildHeader({ breadcrumb = [], summary = '' }) {
  const cols = process.stdout.columns || 60;
  const ruleWidth = Math.max(10, Math.min(60, cols - 2));
  const lines = [GRADIENT_TITLE];
  if (breadcrumb.length) lines.push(styles.muted.render(breadcrumb.join('  ›  ')));
  lines.push(styles.muted.render('─'.repeat(ruleWidth)));
  if (summary) lines.push(styles.muted.render(summary));
  return lines.join('\n');
}

export function buildFooter(hints = []) {
  return styles.muted.render(hints.join('   ·   '));
}

function describe(item) {
  const d = typeof item.description === 'function' ? item.description() : item.description;
  return d ? String(d) : '';
}

function caret(focused) {
  return focused ? CARET : CARET_BLANK;
}

export function buildRow(item, focused) {
  if (item.kind === 'separator') {
    return styles.muted.render('─'.repeat(44));
  }

  if (item.kind === 'back') {
    const text = `← ${item.label}`;
    return caret(focused) + (focused ? styles.accentBold.render(text) : styles.muted.render(text));
  }

  if (item.kind === 'action') {
    const desc = describe(item);
    let row = caret(focused) + (focused ? styles.accentBold.render(item.label) : item.label);
    if (desc) row += '   ' + styles.warning.render(desc);
    return row;
  }

  if (item.kind === 'toggle') {
    const val = Boolean(item.getValue());
    const label = focused ? styles.bold.render(item.label) : item.label;
    let row = caret(focused) + label + '   ' + (val ? styles.successBold.render('ON') : styles.dangerBold.render('OFF'));
    if (focused) row += '   ' + styles.muted.render('Space/Enter to toggle');
    return row;
  }

  if (item.kind === 'picker') {
    const value = item.getValue();
    const display = (item.options.find(([v]) => v === value) || [null, String(value)])[1];
    const valStr = focused ? ` ◀ ${display} ▶` : `   ${display}`;
    const label = focused ? styles.bold.render(item.label) : item.label;
    let row = caret(focused) + label + (focused ? styles.accent2Bold.render(valStr) : styles.accent2.render(valStr));
    if (focused) row += '   ' + styles.muted.render('← → cycle');
    return row;
  }

  if (item.kind === 'number') {
    const value = Number(item.getValue());
    const display = item.isFloat ? `${value.toFixed(1)} s` : String(value);
    const valStr = focused ? ` ◀ ${display} ▶` : `   ${display}`;
    const label = focused ? styles.bold.render(item.label) : item.label;
    let row = caret(focused) + label + (focused ? styles.accent2Bold.render(valStr) : styles.accent2.render(valStr));
    if (focused) row += '   ' + styles.muted.render('← → adjust, Enter to type');
    return row;
  }

  if (item.kind === 'text') {
    const raw = String(item.getValue() ?? '');
    const notSet = !raw || raw.startsWith('your_');
    const display = notSet ? '[not set]' : item.secret ? (raw.length > 10 ? `${raw.slice(0, 4)}…${raw.slice(-4)}` : '***') : raw;
    const label = focused ? styles.bold.render(item.label) : item.label;
    const valStyle = notSet ? (focused ? styles.dangerBold : styles.danger) : focused ? styles.accent2Bold : styles.accent2;
    let row = caret(focused) + label + '   ' + valStyle.render(display);
    if (focused) row += '   ' + styles.muted.render('Enter to edit');
    return row;
  }

  return '';
}

export function buildEditBox(label, text, cursorPos, secret) {
  const display = secret ? '*'.repeat(text.length) : text;
  const before = display.slice(0, cursorPos);
  const cursorChar = cursorPos < display.length ? display[cursorPos] : ' ';
  const after = cursorPos < display.length ? display.slice(cursorPos + 1) : '';
  const content = `${styles.muted.render(label + ': ')}${before}${styles.reverse.render(cursorChar)}${after}`;
  return styles.editBorder.render(content);
}
