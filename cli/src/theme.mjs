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
  // Hot pink/magenta — the Lip Gloss showcase's "active/selected" primary
  // (its status-bar nugget, active-tab, and dialog-button color). New in
  // this palette; nothing used pink before.
  primary: '#FF1493',
  // Deep violet — nudged from #7C6FF0 to sit in the showcase's own
  // highlight range (~#7D56F4) and now specifically the "solid content
  // block" color (borders, the title's leading edge), while `primary` above
  // takes over the "this is active" job it used to share.
  accent: '#7D56F4',
  accent2: '#38BDF8', // cyan — kept as the secondary accent, unchanged
  success: '#22C55E',
  danger: '#F87171',
  warning: '#FBBF24',
  muted: '#6B7280',
  // Header/footer bar backdrop. Was #181428 (violet-black) — shifted to a
  // neutral charcoal, matching the showcase's own status bar (a plain dark
  // gray bar with colorful badges on top, not a tinted bar): the color now
  // lives in the badges, not the bar itself.
  surface: '#2B2B33',
  // Focused-row highlight backdrop. Was #2D2354 (blue-violet) — nudged
  // toward plum so it harmonizes with the new pink `primary` rather than
  // clashing with it.
  selectionBg: '#3A2340',
  // Light text for dark surface/selection backgrounds. Was #D8D4EE —
  // brightened toward the showcase's own off-white (#FFFDF5).
  onSurface: '#F5F3FF',
  // Near-black, used as foreground text on solid pink/violet badge/button
  // backgrounds where light text wouldn't have enough contrast.
  chipFg: '#1A1025',
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

  // Full-width background bars (header/footer chrome) and the focused-row
  // highlight band. Lip Gloss terminates every render() call with a full SGR
  // reset, so a background set only on an *outer* wrapper does not survive
  // through any pre-styled substring nested inside it (verified empirically:
  // wrapping already-colored text in a backgrounded Style leaves the
  // background "punched through" wherever the inner text's own reset fires).
  // So every fragment that needs to sit on one of these backgrounds carries
  // that background itself, rather than relying on an outer wrap — see how
  // render.mjs uses these.
  headerBar: new Style().background(colors.surface).foreground(colors.onSurface),
  footerBar: new Style().background(colors.surface).foreground(colors.muted),
  selBg: new Style().background(colors.selectionBg).foreground(colors.onSurface),
  selBold: new Style().background(colors.selectionBg).foreground(colors.onSurface).bold(true),
  selAccentBold: new Style().background(colors.selectionBg).foreground(colors.accent).bold(true),
  selAccent2Bold: new Style().background(colors.selectionBg).foreground(colors.accent2).bold(true),
  selSuccessBold: new Style().background(colors.selectionBg).foreground(colors.success).bold(true),
  selDangerBold: new Style().background(colors.selectionBg).foreground(colors.danger).bold(true),
  selWarning: new Style().background(colors.selectionBg).foreground(colors.warning),
  selMuted: new Style().background(colors.selectionBg).foreground(colors.muted),

  // Solid "badge" chips — bold text on a fully-saturated background with
  // horizontal padding, the showcase's core UI primitive (status-bar
  // nuggets, the active tab, dialog buttons). Self-contained single
  // render() calls each (no nested pre-styled text inside), so none of the
  // "background punched through by an inner reset" caveat above applies —
  // padding is part of the style itself and gets the same background.
  caretChip: new Style().background(colors.primary).foreground(colors.chipFg).bold(true).padding(0, 1),
  badgePrimary: new Style().background(colors.primary).foreground(colors.chipFg).bold(true).padding(0, 1),
  badgeAccent: new Style().background(colors.accent).foreground(colors.onSurface).bold(true).padding(0, 1),
  badgeAccent2: new Style().background(colors.accent2).foreground(colors.chipFg).bold(true).padding(0, 1),

  // Button-style chips for a future confirmation dialog (none exists yet —
  // no screen builds one — these are prepared so one can be assembled later
  // without inventing new singletons mid-feature).
  buttonPrimary: new Style().background(colors.primary).foreground(colors.chipFg).bold(true).padding(0, 2),
  buttonSecondary: new Style().background(Color('#3C3C3C')).foreground(colors.onSurface).bold(true).padding(0, 2),
};

// A 3-row banner: a blank row, the title itself in bold white, then another
// blank row, all on one solid background — a color block rather than a
// single line of text, so the heading reads as a bigger, more prominent
// banner (a terminal can't change font size, so "larger" here means more of
// the screen given to it: extra vertical rows plus horizontal padding, not
// bigger glyphs). Solid `accent` violet rather than a gradient — it's
// already the color every screen's own title (styles.accentBold) and the
// edit-box border render in, so the banner reads as part of the same
// design instead of introducing its own look.
// Rendered once at module load — the title never changes, so there's no
// reason to re-render it on every redraw.
function renderBanner(text, bgHex, hPad = 3) {
  const bg = Color(bgHex);
  const totalCols = text.length + hPad * 2;
  const textRow = new Style().bold(true).foreground(Color('#FFFFFF')).background(bg).render(text.padStart(text.length + hPad).padEnd(totalCols));
  const blankRow = new Style().background(bg).render(' '.repeat(totalCols));
  return [blankRow, textRow, blankRow].join('\n');
}

export const TITLE_BANNER = renderBanner('Anki Vocabulary Deck Generator', HEX.accent);
