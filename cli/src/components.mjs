// Menu item components — same contract/behavior as tui.py's MenuItem
// subclasses (Action, Toggle, Picker, TextInput, NumberInput, Separator,
// Back), reimplemented against plain ANSI instead of curses.

import { paint, editString } from './ui.mjs';

function focusBg(focused) {
  return focused ? ['bgCyan', 'black'] : [];
}

// parts: [{ text, styles }], padded/truncated to exactly `width` visible chars.
// Each part is styled independently (not the concatenated string) so a
// focused row's background stays a single continuous bgCyan block even
// though foreground styles vary within it.
function buildRow(width, parts) {
  let plain = parts.map((p) => p.text).join('');
  if (plain.length < width) {
    const padStyles = parts.length ? parts[parts.length - 1].styles : [];
    parts = [...parts, { text: ' '.repeat(width - plain.length), styles: padStyles }];
  } else if (plain.length > width) {
    let over = plain.length - width;
    parts = parts.map((p) => ({ ...p }));
    for (let i = parts.length - 1; i >= 0 && over > 0; i--) {
      const cut = Math.min(over, parts[i].text.length);
      parts[i].text = parts[i].text.slice(0, parts[i].text.length - cut);
      over -= cut;
    }
  }
  return parts.map((p) => paint(p.text, ...p.styles)).join('');
}

function clip(text, width) {
  return text.length > width ? text.slice(0, width) : text.padEnd(width);
}

export class Separator {
  constructor(label = '') {
    this.label = label;
    this.selectable = false;
  }
  render(width) {
    let line;
    if (this.label) {
      const pad = Math.max(0, Math.floor((width - this.label.length - 4) / 2));
      line = '─'.repeat(pad) + '  ' + this.label + '  ' + '─'.repeat(pad);
    } else {
      line = '─'.repeat(width);
    }
    return paint(line.slice(0, width), 'dim');
  }
}

export class Back {
  constructor(label = 'Back') {
    this.label = label;
    this.selectable = true;
  }
  render(width, focused) {
    const bg = focusBg(focused);
    const prefix = focused ? '▶ ' : '  ';
    const text = clip(prefix + `← ${this.label}`, width);
    const styles = focused ? [...bg, 'bold'] : ['dim'];
    return buildRow(width, [{ text, styles }]);
  }
  onEnter() {
    return 'back';
  }
}

export class Action {
  constructor(label, handler, description = '') {
    this.label = label;
    this.handler = handler;
    this._desc = description;
    this.selectable = true;
  }
  _description() {
    const d = typeof this._desc === 'function' ? this._desc() : this._desc;
    return String(d || '');
  }
  render(width, focused) {
    const bg = focusBg(focused);
    const prefix = focused ? '▶ ' : '  ';
    const desc = this._description();
    const labelW = Math.max(16, width - prefix.length - desc.length - 6);
    const label = clip(this.label, labelW);
    const parts = [
      { text: prefix, styles: focused ? [...bg, 'cyan', 'bold'] : bg },
      { text: label, styles: focused ? [...bg, 'bold'] : bg },
    ];
    if (desc) {
      parts.push({ text: '    ', styles: bg });
      parts.push({ text: desc, styles: [...bg, 'yellow'] });
    }
    return buildRow(width, parts);
  }
  async onEnter() {
    return await this.handler();
  }
}

export class Toggle {
  constructor(label, configKey, { getConfig, setConfig } = {}) {
    this.label = label;
    this.configKey = configKey;
    this.getConfig = getConfig;
    this.setConfig = setConfig;
    this.selectable = true;
    this.respondsToSpace = true;
  }
  _val() {
    return Boolean(this.getConfig()[this.configKey]);
  }
  async _toggle() {
    await this.setConfig(this.configKey, String(!this._val()), 'bool');
  }
  render(width, focused) {
    const bg = focusBg(focused);
    const val = this._val();
    const prefix = focused ? '▶ ' : '  ';
    const ind = val ? ' ON ' : ' OFF';
    const hintStr = focused ? '  Space/Enter to toggle' : '';
    const labelW = Math.max(10, width - prefix.length - ind.length - 4 - hintStr.length);
    const label = clip(this.label, labelW);
    const parts = [
      { text: prefix, styles: focused ? [...bg, 'cyan', 'bold'] : bg },
      { text: label, styles: bg },
      { text: ' [', styles: [...bg, 'dim'] },
      { text: ind, styles: val ? [...bg, 'green', 'bold'] : [...bg, 'red', 'bold'] },
      { text: ']', styles: [...bg, 'dim'] },
    ];
    if (focused && hintStr) parts.push({ text: hintStr, styles: [...bg, 'dim'] });
    return buildRow(width, parts);
  }
  async onEnter() {
    await this._toggle();
  }
  async onLeft() {
    if (this._val()) await this._toggle();
  }
  async onRight() {
    if (!this._val()) await this._toggle();
  }
}

export class Picker {
  constructor(label, configKey, options, { getConfig, setConfig } = {}) {
    this.label = label;
    this.configKey = configKey;
    this.options = options; // [[value, displayLabel], ...]
    this.getConfig = getConfig;
    this.setConfig = setConfig;
    this.selectable = true;
    this.respondsToSpace = true;
  }
  _idx() {
    const val = this.getConfig()[this.configKey];
    const i = this.options.findIndex(([v]) => v === val);
    return i === -1 ? 0 : i;
  }
  _display() {
    return this.options[this._idx()][1];
  }
  async _set(idx) {
    const n = this.options.length;
    const wrapped = ((idx % n) + n) % n;
    await this.setConfig(this.configKey, this.options[wrapped][0], 'str');
  }
  render(width, focused) {
    const bg = focusBg(focused);
    const prefix = focused ? '▶ ' : '  ';
    const display = this._display();
    const valStr = focused ? ` ◀ ${display} ▶ ` : `   ${display}`;
    const hintStr = focused ? '  ← → cycle' : '';
    const labelW = Math.max(10, width - prefix.length - valStr.length - hintStr.length);
    const label = clip(this.label, labelW);
    const parts = [
      { text: prefix, styles: focused ? [...bg, 'cyan', 'bold'] : bg },
      { text: label, styles: bg },
      { text: valStr, styles: focused ? [...bg, 'yellow', 'bold'] : [...bg, 'yellow'] },
    ];
    if (focused && hintStr) parts.push({ text: hintStr, styles: [...bg, 'dim'] });
    return buildRow(width, parts);
  }
  async onEnter() {
    await this._set(this._idx() + 1);
  }
  async onLeft() {
    await this._set(this._idx() - 1);
  }
  async onRight() {
    await this._set(this._idx() + 1);
  }
}

export class TextInput {
  constructor(label, configKey, { secret = false, getConfig, setConfig } = {}) {
    this.label = label;
    this.configKey = configKey;
    this.secret = secret;
    this.getConfig = getConfig;
    this.setConfig = setConfig;
    this.selectable = true;
  }
  _val() {
    return String(this.getConfig()[this.configKey] ?? '');
  }
  _display() {
    const val = this._val();
    if (!val || val.startsWith('your_')) return '[not set]';
    if (this.secret) return val.length > 10 ? `${val.slice(0, 4)}…${val.slice(-4)}` : '***';
    return val;
  }
  render(width, focused) {
    const bg = focusBg(focused);
    const prefix = focused ? '▶ ' : '  ';
    const display = this._display();
    const notSet = display === '[not set]';
    const hintStr = focused ? '  Enter to edit' : '';
    const valStyles = notSet
      ? (focused ? [...bg, 'red', 'bold'] : [...bg, 'red'])
      : (focused ? [...bg, 'yellow', 'bold'] : [...bg, 'yellow']);
    const labelW = Math.max(10, width - prefix.length - display.length - 4 - hintStr.length);
    const label = clip(this.label, labelW);
    const parts = [
      { text: prefix, styles: focused ? [...bg, 'cyan', 'bold'] : bg },
      { text: label, styles: bg },
      { text: '  ', styles: bg },
      { text: display, styles: valStyles },
    ];
    if (focused && hintStr) parts.push({ text: hintStr, styles: [...bg, 'dim'] });
    return buildRow(width, parts);
  }
  async onEnter() {
    const newVal = await editString(this.label, this._val(), this.secret);
    if (newVal !== null && newVal !== this._val()) {
      await this.setConfig(this.configKey, newVal, 'str');
    }
  }
}

export class NumberInput {
  constructor(label, configKey, { minVal = 0, step = 1, isFloat = false, getConfig, setConfig } = {}) {
    this.label = label;
    this.configKey = configKey;
    this.minVal = minVal;
    this.step = step;
    this.isFloat = isFloat;
    this.getConfig = getConfig;
    this.setConfig = setConfig;
    this.selectable = true;
    this.respondsToSpace = true;
  }
  _val() {
    return Number(this.getConfig()[this.configKey] ?? this.minVal);
  }
  _display() {
    const v = this._val();
    return this.isFloat ? `${v.toFixed(1)} s` : String(v);
  }
  async _clampSet(val) {
    const clamped = this.isFloat
      ? Math.round(Math.max(this.minVal, val) * 10) / 10
      : Math.max(this.minVal, Math.round(val));
    await this.setConfig(this.configKey, String(clamped), this.isFloat ? 'float' : 'int');
  }
  render(width, focused) {
    const bg = focusBg(focused);
    const prefix = focused ? '▶ ' : '  ';
    const display = this._display();
    const valStr = focused ? ` ◀ ${display} ▶ ` : `   ${display}`;
    const hintStr = focused ? '  ← → adjust, Enter to type' : '';
    const labelW = Math.max(10, width - prefix.length - valStr.length - hintStr.length);
    const label = clip(this.label, labelW);
    const parts = [
      { text: prefix, styles: focused ? [...bg, 'cyan', 'bold'] : bg },
      { text: label, styles: bg },
      { text: valStr, styles: focused ? [...bg, 'yellow', 'bold'] : [...bg, 'yellow'] },
    ];
    if (focused && hintStr) parts.push({ text: hintStr, styles: [...bg, 'dim'] });
    return buildRow(width, parts);
  }
  async onEnter() {
    const raw = await editString(this.label, String(this._val()));
    if (raw !== null) {
      const num = Number(raw);
      if (!Number.isNaN(num)) await this._clampSet(num);
    }
  }
  async onLeft() {
    await this._clampSet(this._val() - this.step);
  }
  async onRight() {
    await this._clampSet(this._val() + this.step);
  }
}
