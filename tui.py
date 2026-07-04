"""
tui.py — Curses-based interactive menu for Anki Deck Generator.

Cross-platform: Linux, macOS, Windows (install windows-curses on Windows).
Falls back gracefully if the terminal does not support curses.
"""

import curses
import config as _cfg

# ─────────────────────────────────────────────
#  Color pair registry
# ─────────────────────────────────────────────

_CP = {
    'normal': 1,
    'focus':  2,   # highlighted row (black on cyan)
    'cyan':   3,
    'green':  4,
    'red':    5,
    'yellow': 6,
    'dim':    7,
    'title':  8,   # banner title (cyan on black)
}

# Single shared curses context so nested run_menu() calls reuse the window
_ctx = {'stdscr': None}


def _cp(name):
    return curses.color_pair(_CP[name])


def _init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(_CP['normal'], -1,                  -1)
    curses.init_pair(_CP['focus'],  curses.COLOR_BLACK,  curses.COLOR_CYAN)
    curses.init_pair(_CP['cyan'],   curses.COLOR_CYAN,   -1)
    curses.init_pair(_CP['green'],  curses.COLOR_GREEN,  -1)
    curses.init_pair(_CP['red'],    curses.COLOR_RED,    -1)
    curses.init_pair(_CP['yellow'], curses.COLOR_YELLOW, -1)
    # Bright black (gray) for dimmed text — pair 7
    try:
        curses.init_pair(_CP['dim'], 8, -1)
    except Exception:
        curses.init_pair(_CP['dim'], curses.COLOR_WHITE, -1)
    curses.init_pair(_CP['title'], curses.COLOR_CYAN, curses.COLOR_BLACK)


# ─────────────────────────────────────────────
#  Banner and chrome
# ─────────────────────────────────────────────

def _draw_banner(win):
    h, w = win.getmaxyx()
    try:
        border = '═' * max(0, w - 2)
        win.addstr(0, 0, ('╔' + border + '╗')[:w], _cp('cyan'))

        title = '  Anki Vocabulary Deck Generator  v2.0'
        win.addstr(1, 0, '║', _cp('cyan'))
        win.addstr(1, 1, title.ljust(w - 2)[:w - 2], _cp('title') | curses.A_BOLD)
        win.addstr(1, w - 1, '║', _cp('cyan'))

        win.addstr(2, 0, ('╠' + border + '╣')[:w], _cp('cyan'))

        info = (f'  {_cfg.SOURCE_LANG.upper()} -> {_cfg.TARGET_LANG}'
                f'   |   template: {_cfg.CARD_TEMPLATE}'
                f'   |   type: {_cfg.CARD_TYPE}')
        win.addstr(3, 0, '║', _cp('cyan'))
        win.addstr(3, 1, info.ljust(w - 2)[:w - 2], _cp('dim'))
        win.addstr(3, w - 1, '║', _cp('cyan'))

        win.addstr(4, 0, ('╚' + border + '╝')[:w], _cp('cyan'))
    except curses.error:
        pass


def _draw_statusbar(win):
    h, w = win.getmaxyx()
    bar = '  ↑↓ navigate   ←→ change value   Enter select   Esc / q  back  '
    try:
        win.addstr(h - 1, 0, bar.ljust(w - 1)[:w - 1], _cp('focus'))
    except curses.error:
        pass


# ─────────────────────────────────────────────
#  Inline text editor (used by TextInput)
# ─────────────────────────────────────────────

def _edit_string(win, label, initial='', secret=False):
    """
    Draw a text-input box at the bottom of win and collect user input.
    Returns the new string on Enter, or None on Esc.
    Supports: Backspace, Delete, ←→, Home, End, printable ASCII.
    """
    h, w = win.getmaxyx()
    box_y = h - 6
    iw    = w - 4   # inner box width
    fx    = 2       # field x offset inside box

    def _draw_box(buf, cpos):
        try:
            border = '═' * iw
            win.addstr(box_y,     1, '╔' + border + '╗', _cp('cyan'))
            prompt = f'  {label}:'
            win.addstr(box_y + 1, 1, '║', _cp('cyan'))
            win.addstr(box_y + 1, 2, prompt.ljust(iw)[:iw], _cp('cyan') | curses.A_BOLD)
            win.addstr(box_y + 1, w - 2, '║', _cp('cyan'))
            win.addstr(box_y + 2, 1, '║', _cp('cyan'))
            # draw field background
            win.addstr(box_y + 2, 2, ' ' * iw, _cp('yellow') | curses.A_UNDERLINE)
            win.addstr(box_y + 2, w - 2, '║', _cp('cyan'))
            hint = '  Enter = confirm   Esc = cancel'
            win.addstr(box_y + 3, 1, '║', _cp('cyan'))
            win.addstr(box_y + 3, 2, hint.ljust(iw)[:iw], _cp('dim'))
            win.addstr(box_y + 3, w - 2, '║', _cp('cyan'))
            win.addstr(box_y + 4, 1, '╚' + border + '╝', _cp('cyan'))
        except curses.error:
            pass

        # Draw text inside field
        text     = ''.join(buf)
        display  = '*' * len(text) if secret else text
        field_w  = iw - 2
        start    = max(0, cpos - field_w + 1)
        visible  = display[start:start + field_w]
        try:
            win.addstr(box_y + 2, fx + 1,
                       visible.ljust(field_w)[:field_w],
                       _cp('yellow') | curses.A_UNDERLINE)
            cursor_x = fx + 1 + (cpos - start)
            win.move(box_y + 2, min(cursor_x, w - 3))
        except curses.error:
            pass
        win.refresh()

    buf  = list(initial)
    cpos = len(buf)
    curses.curs_set(1)
    _draw_box(buf, cpos)

    result = None
    while True:
        ch = win.getch()
        if ch in (curses.KEY_ENTER, 10, 13):
            result = ''.join(buf)
            break
        elif ch == 27:   # Esc
            break
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            if cpos > 0:
                buf.pop(cpos - 1)
                cpos -= 1
        elif ch == curses.KEY_DC:
            if cpos < len(buf):
                buf.pop(cpos)
        elif ch == curses.KEY_LEFT:
            cpos = max(0, cpos - 1)
        elif ch == curses.KEY_RIGHT:
            cpos = min(len(buf), cpos + 1)
        elif ch == curses.KEY_HOME:
            cpos = 0
        elif ch == curses.KEY_END:
            cpos = len(buf)
        elif 32 <= ch < 127:
            buf.insert(cpos, chr(ch))
            cpos += 1
        _draw_box(buf, cpos)

    curses.curs_set(0)

    # Erase input box
    for i in range(5):
        try:
            win.move(box_y + i, 0)
            win.clrtoeol()
        except curses.error:
            pass

    return result


# ─────────────────────────────────────────────
#  MenuItem base and concrete types
# ─────────────────────────────────────────────

class MenuItem:
    """Base class — override render() and on_enter()."""
    selectable = True

    def render(self, win, y, x, focused, avail_w):
        pass

    def on_enter(self, win):
        """Called on Enter. Return 'back' to exit the menu."""
        return None

    def on_left(self):
        """Called on ← arrow."""

    def on_right(self):
        """Called on → arrow."""


class Separator(MenuItem):
    """A non-selectable horizontal rule, optionally with a label."""
    selectable = False

    def __init__(self, label=''):
        self.label = label

    def render(self, win, y, x, focused, avail_w):
        try:
            if self.label:
                pad  = max(0, (avail_w - len(self.label) - 4) // 2)
                line = ('─' * pad + '  ' + self.label + '  ' + '─' * pad)
            else:
                line = '─' * avail_w
            win.addstr(y, x, line[:avail_w], _cp('dim'))
        except curses.error:
            pass


class Back(MenuItem):
    """Exits the current menu."""

    def __init__(self, label='Back'):
        self.label = label

    def render(self, win, y, x, focused, avail_w):
        prefix = '▶ ' if focused else '  '
        text   = f'← {self.label}'
        attr   = (_cp('focus') | curses.A_BOLD) if focused else _cp('dim')
        try:
            win.addstr(y, x, (prefix + text).ljust(avail_w)[:avail_w], attr)
        except curses.error:
            pass

    def on_enter(self, win):
        return 'back'


class Action(MenuItem):
    """
    Calls a function when Enter is pressed.

    print_mode=True: temporarily suspends curses so the function can
    print to the terminal normally (for generate / export / stats screens).
    description: string or callable → shown as a dim value on the right.
    """

    def __init__(self, label, func, description=None, print_mode=False):
        self.label      = label
        self.func       = func
        self._desc      = description
        self.print_mode = print_mode

    def _get_desc(self):
        d = self._desc() if callable(self._desc) else (self._desc or '')
        return str(d)

    def render(self, win, y, x, focused, avail_w):
        prefix      = '▶ ' if focused else '  '
        prefix_attr = (_cp('cyan') | curses.A_BOLD) if focused else 0
        label_attr  = curses.A_BOLD if focused else 0
        desc        = self._get_desc()

        label_w = max(16, avail_w - len(prefix) - len(desc) - 6)
        label_p = self.label.ljust(label_w)[:label_w]

        try:
            win.addstr(y, x, prefix, prefix_attr)
            cx = x + len(prefix)
            win.addstr(y, cx, label_p, label_attr)
            cx += len(label_p)
            if desc:
                win.addstr(y, cx, '    ', 0)
                cx += 4
                win.addstr(y, cx, desc[:avail_w - cx + x], _cp('yellow'))
        except curses.error:
            pass

    def on_enter(self, win):
        if self.print_mode:
            # Suspend curses, run print-based function, restore curses
            win.clear()
            win.refresh()
            curses.endwin()
            saved = _ctx['stdscr']
            _ctx['stdscr'] = None
            try:
                self.func()
            finally:
                _ctx['stdscr'] = saved
                # Restore curses state after returning
                saved.keypad(True)
                _init_colors()
                curses.curs_set(0)
        else:
            self.func()
        return None


class Toggle(MenuItem):
    """Boolean ON/OFF switch for a config key. Toggle with Enter, Space, or ←→."""

    def __init__(self, label, config_key, hint=''):
        self.label      = label
        self.config_key = config_key
        self.hint       = hint

    def _val(self):
        return bool(getattr(_cfg, self.config_key, False))

    def _toggle(self):
        from main import write_config
        write_config(self.config_key, not self._val())

    def render(self, win, y, x, focused, avail_w):
        val         = self._val()
        prefix      = '▶ ' if focused else '  '
        prefix_attr = (_cp('cyan') | curses.A_BOLD) if focused else 0
        ind         = ' ON ' if val else ' OFF'
        ind_attr    = (_cp('green') | curses.A_BOLD) if val else (_cp('red') | curses.A_BOLD)
        hint_str    = '  Space/Enter to toggle' if focused else ''

        label_w = max(10, avail_w - len(prefix) - len(ind) - 4 - len(hint_str))
        label_p = self.label.ljust(label_w)[:label_w]

        try:
            win.addstr(y, x, prefix, prefix_attr)
            cx = x + len(prefix)
            win.addstr(y, cx, label_p)
            cx += len(label_p)
            win.addstr(y, cx, ' [', _cp('dim'))
            cx += 2
            win.addstr(y, cx, ind, ind_attr)
            cx += len(ind)
            win.addstr(y, cx, ']', _cp('dim'))
            cx += 1
            if focused and hint_str:
                win.addstr(y, cx, hint_str, _cp('dim'))
        except curses.error:
            pass

    def on_enter(self, win):
        self._toggle()

    def on_left(self):
        if self._val():
            self._toggle()

    def on_right(self):
        if not self._val():
            self._toggle()


class Picker(MenuItem):
    """
    Cycle through a fixed list of options with ← → or Enter.
    options: list of (config_value, display_label) tuples.
    """

    def __init__(self, label, config_key, options, hint=''):
        self.label      = label
        self.config_key = config_key
        self.options    = options
        self.hint       = hint

    def _idx(self):
        val = getattr(_cfg, self.config_key, self.options[0][0])
        for i, (v, _) in enumerate(self.options):
            if v == val:
                return i
        return 0

    def _display(self):
        return self.options[self._idx()][1]

    def _set(self, idx):
        from main import write_config
        write_config(self.config_key, self.options[idx % len(self.options)][0])

    def render(self, win, y, x, focused, avail_w):
        prefix      = '▶ ' if focused else '  '
        prefix_attr = (_cp('cyan') | curses.A_BOLD) if focused else 0
        display     = self._display()

        if focused:
            val_str  = f' ◀ {display} ▶ '
            val_attr = _cp('yellow') | curses.A_BOLD
            hint_str = '  ← → cycle'
        else:
            val_str  = f'   {display}'
            val_attr = _cp('yellow')
            hint_str = ''

        label_w = max(10, avail_w - len(prefix) - len(val_str) - len(hint_str))
        label_p = self.label.ljust(label_w)[:label_w]

        try:
            win.addstr(y, x, prefix, prefix_attr)
            cx = x + len(prefix)
            win.addstr(y, cx, label_p)
            cx += len(label_p)
            win.addstr(y, cx, val_str, val_attr)
            cx += len(val_str)
            if focused and hint_str:
                win.addstr(y, cx, hint_str, _cp('dim'))
        except curses.error:
            pass

    def on_enter(self, win):
        self._set(self._idx() + 1)

    def on_left(self):
        self._set(self._idx() - 1)

    def on_right(self):
        self._set(self._idx() + 1)


class TextInput(MenuItem):
    """
    Text field. Enter opens the inline editor.
    secret=True masks the value (for API keys).
    """

    def __init__(self, label, config_key, hint='', secret=False):
        self.label      = label
        self.config_key = config_key
        self.hint       = hint
        self.secret     = secret

    def _val(self):
        return str(getattr(_cfg, self.config_key, ''))

    def _display(self):
        val = self._val()
        if not val or val.startswith('your_'):
            return '[not set]'
        if self.secret:
            return val[:4] + '…' + val[-4:] if len(val) > 10 else '***'
        return val

    def render(self, win, y, x, focused, avail_w):
        prefix      = '▶ ' if focused else '  '
        prefix_attr = (_cp('cyan') | curses.A_BOLD) if focused else 0
        display     = self._display()
        hint_str    = '  Enter to edit' if focused else ''
        val_attr    = (_cp('yellow') | curses.A_BOLD) if focused else _cp('yellow')

        not_set = display == '[not set]'
        if not_set:
            val_attr = (_cp('red') | curses.A_BOLD) if focused else _cp('red')

        label_w = max(10, avail_w - len(prefix) - len(display) - 4 - len(hint_str))
        label_p = self.label.ljust(label_w)[:label_w]

        try:
            win.addstr(y, x, prefix, prefix_attr)
            cx = x + len(prefix)
            win.addstr(y, cx, label_p)
            cx += len(label_p)
            win.addstr(y, cx, '  ')
            cx += 2
            win.addstr(y, cx, display, val_attr)
            cx += len(display)
            if focused and hint_str:
                win.addstr(y, cx, hint_str, _cp('dim'))
        except curses.error:
            pass

    def on_enter(self, win):
        from main import write_config
        new_val = _edit_string(win, self.label, self._val(), secret=self.secret)
        if new_val is not None and new_val != self._val():
            write_config(self.config_key, new_val)


class NumberInput(MenuItem):
    """
    Numeric field (int or float).
    ← → nudge by step. Enter opens inline editor for exact value.
    """

    def __init__(self, label, config_key, hint='', min_val=0, step=1, is_float=False):
        self.label      = label
        self.config_key = config_key
        self.hint       = hint
        self.min_val    = min_val
        self.step       = step
        self.is_float   = is_float

    def _val(self):
        return getattr(_cfg, self.config_key, self.min_val)

    def _display(self):
        v = self._val()
        return f'{v:.1f} s' if self.is_float else str(v)

    def _clamp_set(self, val):
        from main import write_config
        if self.is_float:
            val = round(max(float(self.min_val), float(val)), 1)
        else:
            val = max(int(self.min_val), int(val))
        write_config(self.config_key, val)

    def render(self, win, y, x, focused, avail_w):
        prefix      = '▶ ' if focused else '  '
        prefix_attr = (_cp('cyan') | curses.A_BOLD) if focused else 0
        display     = self._display()
        hint_str    = '  ← → adjust, Enter to type' if focused else ''

        if focused:
            val_str  = f' ◀ {display} ▶ '
            val_attr = _cp('yellow') | curses.A_BOLD
        else:
            val_str  = f'   {display}'
            val_attr = _cp('yellow')

        label_w = max(10, avail_w - len(prefix) - len(val_str) - len(hint_str))
        label_p = self.label.ljust(label_w)[:label_w]

        try:
            win.addstr(y, x, prefix, prefix_attr)
            cx = x + len(prefix)
            win.addstr(y, cx, label_p)
            cx += len(label_p)
            win.addstr(y, cx, val_str, val_attr)
            cx += len(val_str)
            if focused and hint_str:
                win.addstr(y, cx, hint_str, _cp('dim'))
        except curses.error:
            pass

    def on_enter(self, win):
        raw = _edit_string(win, self.label, str(self._val()))
        if raw is not None:
            try:
                self._clamp_set(float(raw) if self.is_float else int(raw))
            except ValueError:
                pass

    def on_left(self):
        self._clamp_set(self._val() - self.step)

    def on_right(self):
        self._clamp_set(self._val() + self.step)


# ─────────────────────────────────────────────
#  Core menu loop
# ─────────────────────────────────────────────

def _first_selectable(items):
    for i, item in enumerate(items):
        if item.selectable:
            return i
    return 0


def _next_sel(items, current, direction):
    n = len(items)
    idx = (current + direction) % n
    for _ in range(n):
        if items[idx].selectable:
            return idx
        idx = (idx + direction) % n
    return current


def _run_inner(title, items, stdscr):
    current = _first_selectable(items)

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()

        _draw_banner(stdscr)

        # Section heading
        try:
            stdscr.addstr(6, 2, title, _cp('cyan') | curses.A_BOLD)
            stdscr.addstr(7, 2, ('─' * (w - 4))[:w - 4], _cp('dim'))
        except curses.error:
            pass

        start_y = 9
        avail_w = w - 4

        # Render items (scroll if needed — simple window starting from top)
        visible_count = max(1, h - start_y - 2)
        scroll_start  = max(0, current - visible_count + 1)

        for rel, i in enumerate(range(scroll_start, min(len(items), scroll_start + visible_count))):
            y       = start_y + rel
            focused = (i == current)
            if focused:
                try:
                    stdscr.addstr(y, 0, ' ' * (w - 1), _cp('focus'))
                except curses.error:
                    pass
            items[i].render(stdscr, y, 2, focused, avail_w)

        _draw_statusbar(stdscr)
        stdscr.refresh()

        key = stdscr.getch()

        if key == curses.KEY_UP:
            current = _next_sel(items, current, -1)
        elif key == curses.KEY_DOWN:
            current = _next_sel(items, current, 1)
        elif key in (curses.KEY_ENTER, 10, 13):
            result = items[current].on_enter(stdscr)
            if result == 'back':
                break
        elif key == curses.KEY_LEFT:
            items[current].on_left()
        elif key == curses.KEY_RIGHT:
            items[current].on_right()
        elif key in (ord(' '),):
            # Space: toggle booleans, cycle pickers
            item = items[current]
            if isinstance(item, (Toggle, Picker, NumberInput)):
                item.on_enter(stdscr)
        elif key in (27, ord('q')):   # Esc or q
            break


# ─────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────

def run_menu(title, items):
    """
    Display an interactive menu with arrow-key navigation.

    Handles nested calls: if curses is already running (e.g. called from
    an Action item), the existing window is reused transparently.
    """
    if _ctx['stdscr'] is not None:
        # Nested: reuse the current curses window
        _run_inner(title, items, _ctx['stdscr'])
        return

    def _wrapper(stdscr):
        _ctx['stdscr'] = stdscr
        try:
            _init_colors()
            curses.curs_set(0)
            stdscr.keypad(True)
            _run_inner(title, items, stdscr)
        finally:
            _ctx['stdscr'] = None

    try:
        curses.wrapper(_wrapper)
    except curses.error:
        # Terminal doesn't support curses (e.g. piped output)
        pass
