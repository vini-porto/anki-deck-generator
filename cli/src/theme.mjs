// Palette + Style singletons built on Lip Gloss (@charmland/lipgloss, a
// WASM build of the real Go charmbracelet/lipgloss). Deliberately not the
// tui.py cyan/yellow curses palette — see CLAUDE.md § JavaScript TUI.
//
// Style objects are held here as long-lived module-level singletons, never
// created-and-discarded per redraw. The WASM side has its own Go GC with no
// visibility into JS reachability — a `new Style()` that goes out of scope
// in JS can get collected out from under a still-cached integer handle,
// which surfaced as a real "type assert failed" WASM panic under a redraw
// loop that minted a fresh Style per row per keystroke. Precreating a fixed
// set of styles and reusing them for the process lifetime avoids that
// entirely (and is also just how Lip Gloss is meant to be used).

import { Style, Color, roundedBorder } from '@charmland/lipgloss';

export const HEX = {
  accent: '#7C6FF0',
  accent2: '#38BDF8',
  success: '#22C55E',
  danger: '#F87171',
  warning: '#FBBF24',
  muted: '#6B7280',
};

const colors = Object.fromEntries(Object.entries(HEX).map(([key, hex]) => [key, Color(hex)]));

export const styles = {
  muted: new Style().foreground(colors.muted),
  warning: new Style().foreground(colors.warning),
  warningBold: new Style().foreground(colors.warning).bold(true),
  success: new Style().foreground(colors.success),
  danger: new Style().foreground(colors.danger),
  accent2: new Style().foreground(colors.accent2),
  accent2Bold: new Style().foreground(colors.accent2).bold(true),
  accentBold: new Style().foreground(colors.accent).bold(true),
  successBold: new Style().foreground(colors.success).bold(true),
  dangerBold: new Style().foreground(colors.danger).bold(true),
  bold: new Style().bold(true),
  reverse: new Style().reverse(true),
  editBorder: new Style().border(roundedBorder()).borderForeground(colors.accent).padding(0, 1),
};

function hexToRgb(hex) {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function lerp(a, b, t) {
  return Math.round(a + (b - a) * t);
}

function toHex(n) {
  return n.toString(16).padStart(2, '0');
}

function hexLerp(from, to, t) {
  const [r1, g1, b1] = hexToRgb(from);
  const [r2, g2, b2] = hexToRgb(to);
  return `#${toHex(lerp(r1, r2, t))}${toHex(lerp(g1, g2, t))}${toHex(lerp(b1, b2, t))}`;
}

// Rendered once at module load — the title string never changes, so there's
// no reason to re-mint ~30 per-character Style objects on every redraw.
function renderGradientTitle(text, fromHex, toHex) {
  const glyph = new Style().bold(true);
  const chars = Array.from(text);
  const n = Math.max(1, chars.length - 1);
  return chars.map((ch, i) => glyph.foreground(Color(hexLerp(fromHex, toHex, i / n))).render(ch)).join('');
}

export const GRADIENT_TITLE = renderGradientTitle('Anki Vocabulary Deck Generator', HEX.accent, HEX.accent2);
