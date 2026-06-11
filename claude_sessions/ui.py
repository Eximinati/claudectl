import os
import sys
import msvcrt
import time
import ctypes

from .config import W, EFFORTS, EFFORT_LABELS, MODELS, MODEL_LABELS
from .config import C_RESET, C_TITLE, C_SEL, C_DIM, C_SRCH, C_BOLD, C_GREEN
from .config import load_settings, save_settings, find_editor, get_claude_exe, settings_file
from .config import use_16color_fallback
from .sessions import load_extra_paths, save_extra_paths
from . import render


# ── VT mode ──────────────────────────────────────────────────

_VT_ENABLED = False

def _enable_vt_mode():
    global _VT_ENABLED
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            if kernel32.SetConsoleMode(handle, mode.value | 0x0004):
                _VT_ENABLED = True
    except Exception:
        pass
    if not _VT_ENABLED:
        use_16color_fallback()

_enable_vt_mode()


def _cls():
    """Clear screen — ANSI (instant, no subprocess) if VT enabled, else fallback.
    Also invalidates the frame cache: any raw-print screen that starts with
    _cls() forces the next render_frame() to repaint fully."""
    render.invalidate()
    if _VT_ENABLED:
        try:
            sys.stdout.write('\x1b[2J\x1b[H')
            sys.stdout.flush()
        except Exception:
            pass
    else:
        os.system('cls')


# ── keyboard input ───────────────────────────────────────────
# Events returned by wait_event()/poll_event():
#   ('up',) ('down',) ('left',) ('right',) ('enter',) ('esc',)
#   ('back',) ('del',) ('char', c)

def _key_event():
    key = ord(msvcrt.getch())
    if key in (0, 224):
        k2 = ord(msvcrt.getch())
        return {72: ('up',), 80: ('down',), 75: ('left',), 77: ('right',),
                83: ('del',)}.get(k2, None)
    if key == 13: return ('enter',)
    if key == 27: return ('esc',)
    if key == 8:  return ('back',)
    if 32 <= key <= 126 or key > 127:
        try:
            return ('char', chr(key))
        except ValueError:
            return None
    return None


def wait_event():
    """Block until a meaningful input event arrives."""
    while True:
        ev = _key_event()
        if ev:
            return ev


def poll_event():
    """Non-blocking: return an event if one is pending, else None."""
    if msvcrt.kbhit():
        return _key_event()
    return None


def flush_input():
    while msvcrt.kbhit():
        msvcrt.getch()


def pause(msg='  Press Enter to continue...'):
    """Event-based pause (raw output — invalidates the frame cache)."""
    try:
        print(msg)
    except Exception:
        pass
    flush_input()
    while wait_event()[0] not in ('enter', 'esc'):
        pass
    render.invalidate()


def flash(msg, ok=True, secs=0.8):
    """One-line transient feedback shown after an action (✔/✘ + message)."""
    icon = f"{C_GREEN}✔{C_RESET}" if ok else "✘"
    try:
        if render.screen_active():
            rows = render.frame_height()
            sys.stdout.write(f'\x1b[{rows};1H\x1b[K  {icon} {render.trunc(msg, render.content_width() - 6)}')
        else:
            sys.stdout.write(f"\n  {icon} {msg}\n")
        sys.stdout.flush()
    except Exception:
        pass
    time.sleep(secs)
    flush_input()
    render.invalidate()


# ── UI primitives ────────────────────────────────────────────

def text_input(prompt, default=''):
    flush_input()
    buf = list(default)
    while True:
        frame = [
            render.header('CLAUDECTL', 'INPUT'),
            '',
            f"  {C_TITLE}{prompt}{C_RESET}",
            '',
            f"  {C_SEL}>{C_RESET} {''.join(buf)}{C_SRCH}▌{C_RESET}",
            '',
            render.hint_bar("ENTER confirm   ESC cancel   BACKSPACE delete"),
        ]
        render.render_frame(frame)
        ev = wait_event()
        if ev[0] == 'enter':
            return ''.join(buf).strip()
        elif ev[0] == 'esc':
            return None
        elif ev[0] == 'back':
            if buf: buf.pop()
        elif ev[0] == 'char':
            buf.append(ev[1])


def menu(items, title, footer='', footer_fn=None):
    """Arrow-key menu with live footer and persistent search bar.
    items: list of (label, value). value=None = non-selectable separator.
    Any printable key goes to the search bar (no hotkeys in main menu)."""

    nav_pos    = 0
    search_str = ''

    def _filtered():
        if not search_str:
            return items
        fl = search_str.lower()
        result = [(l, v) for l, v in items
                  if v is not None and fl in l.lower()]
        extras = [(l, v) for l, v in items
                  if v == '__global_claude_md__' and (l, v) not in result]
        return (result + extras) if result else items

    def _nav_idx(disp):
        return [i for i, (_, v) in enumerate(disp) if v is not None]

    def _build(current_footer):
        disp = _filtered()
        ni   = _nav_idx(disp)
        cur  = ni[min(nav_pos, len(ni) - 1)] if ni else -1

        frame = [render.header('CLAUDECTL', title), '']

        if search_str:
            frame.append(f"  {C_SRCH}[ {search_str}▌ ]{C_RESET}")
        else:
            frame.append(f"  {C_DIM}[ search... ]{C_RESET}")
        frame.append('')

        for i, (label, val) in enumerate(disp):
            if val is None:
                frame.append(f"  {C_DIM}{render.trunc(label, render.content_width() - 2)}{C_RESET}")
            else:
                frame.append(render.row(label, selected=(i == cur)))

        frame.append('')
        if search_str:
            hint = "↑↓ navigate   ENTER select   BACKSPACE delete   ESC clear"
        else:
            hint = "↑↓ navigate   ENTER select   type to search   ESC back"
        frame.append(render.hint_bar(hint))
        frame.append(current_footer if current_footer else '')   # stable footer slot
        return frame

    current_footer = footer_fn() if footer_fn else footer
    render.render_frame(_build(current_footer))
    _last_footer = current_footer
    _footer_done = False   # True after MCP resolves — stop polling

    while True:
        ev = poll_event()
        if ev is None:
            if footer_fn and not _footer_done:
                current = footer_fn()
                if current != _last_footer:
                    _last_footer = current
                    _footer_done = True   # update exactly once
                    render.render_frame(_build(current))   # diff = footer line only
            time.sleep(0.05)
            continue

        disp = _filtered()
        ni   = _nav_idx(disp)

        if ev[0] in ('up', 'down'):
            if ni:
                step = -1 if ev[0] == 'up' else 1
                nav_pos = (min(nav_pos, len(ni) - 1) + step) % len(ni)
        elif ev[0] == 'enter':
            if ni:
                return disp[ni[min(nav_pos, len(ni) - 1)]][1]
            return None
        elif ev[0] == 'esc':
            if search_str:
                search_str = ''
                nav_pos    = 0
            else:
                return None
        elif ev[0] == 'back':
            if search_str:
                search_str = search_str[:-1]
                nav_pos    = 0
        elif ev[0] == 'char':
            search_str += ev[1]
            nav_pos    = 0

        render.render_frame(_build(_last_footer))


def help_screen():
    """Static hotkey reference. ENTER/ESC returns."""
    frame = [
        render.header('CLAUDECTL', 'HELP'),
        '',
        f"  {C_BOLD}Main screen{C_RESET}",
        f"    ↑↓ navigate    ENTER open project / resume    ESC exit",
        f"    type to search projects    ★/☆ quick-resume recent sessions",
        '',
        f"  {C_BOLD}Sessions screen{C_RESET}",
        f"    ↑↓ navigate    ENTER resume    ESC back    type to filter",
        f"    r  rename session         d  delete session",
        f"    f  fork session           p  extra PATH entries",
        f"    c  scaffold CLAUDE.md     a  AI-generate CLAUDE.md",
        f"    s  system prompt          ?  this help",
        '',
        f"  {C_BOLD}Launch options{C_RESET}",
        f"    ↑↓ switch field    ← → cycle value    ENTER launch    ESC back",
        '',
        f"  {C_DIM}Settings file: {render.trunc(settings_file, render.content_width() - 20)}{C_RESET}",
        '',
        render.hint_bar("ENTER / ESC go back"),
    ]
    render.render_frame(frame)
    flush_input()
    while wait_event()[0] not in ('enter', 'esc'):
        pass


def settings_menu():
    """Edit ~/.claude/claudectl.json interactively."""
    while True:
        s = load_settings()
        wv = render.content_width() - 22
        editor_now = render.trunc(s['editor'] or (find_editor() or 'NOT FOUND'), wv)
        claude_now = render.trunc(s['claude_exe'] or (get_claude_exe() or 'NOT FOUND'), wv)
        eff = s['default_effort'] or 'default'
        mod = s['default_model'] or 'default'
        items = [
            (f"Editor      :  {editor_now}", 'editor'),
            (f"claude.exe  :  {claude_now}", 'claude'),
            (f"Effort      :  {eff}   {C_DIM}(preselected in launch options){C_RESET}", 'effort'),
            (f"Model       :  {mod}   {C_DIM}(preselected in launch options){C_RESET}", 'model'),
            (f"{'─' * W}", None),
            (f"Back", 'back'),
        ]
        sel = menu(items, "SETTINGS")
        if not sel or sel == 'back':
            return

        if sel == 'editor':
            v = text_input("Editor path (blank = auto-detect):", default=s['editor'])
            if v is not None:
                if v and not os.path.exists(v):
                    flash(f"Path not found: {v}", ok=False, secs=1.2)
                else:
                    s['editor'] = v
                    save_settings(s)
                    flash("Saved")
        elif sel == 'claude':
            v = text_input("claude.exe path (blank = auto-detect):", default=s['claude_exe'])
            if v is not None:
                if v and not os.path.exists(v):
                    flash(f"Path not found: {v}", ok=False, secs=1.2)
                else:
                    s['claude_exe'] = v
                    save_settings(s)
                    flash("Saved")
        elif sel in ('effort', 'model'):
            values, labels = (EFFORTS, EFFORT_LABELS) if sel == 'effort' else (MODELS, MODEL_LABELS)
            pick = menu([(l, v if v else '__default__') for l, v in zip(labels, values)],
                        f"DEFAULT {sel.upper()}")
            if pick is not None:
                s[f'default_{sel}'] = '' if pick == '__default__' else pick
                save_settings(s)
                flash("Saved")


# ── feature menus ────────────────────────────────────────────

def paths_menu(proj_folder, project_name):
    while True:
        paths = load_extra_paths(proj_folder)
        items = [(f"{'─' * W}", None)]
        for p in paths:
            items.append((render.trunc(p, render.content_width() - 8), f"path:{p}"))
        if not paths:
            items.append((f"(no extra paths configured)", None))
        items += [(f"{'─' * W}", None), (f"+ Add new path", 'add'), (f"Back", 'back')]

        nav_indices = [i for i, (_, v) in enumerate(items) if v is not None]
        nav_pos = 0
        redraw = False
        while not redraw:
            cur = nav_indices[nav_pos]
            frame = [render.header('CLAUDECTL', project_name, 'EXTRA PATHS'), '']
            for i, (label, val) in enumerate(items):
                if val is None:
                    frame.append(f"  {C_DIM}{label}{C_RESET}")
                else:
                    frame.append(render.row(label, selected=(i == cur)))
            frame.append('')
            frame.append(render.hint_bar("↑↓ navigate   ENTER select   DEL remove   ESC back"))
            render.render_frame(frame)

            ev = wait_event()
            activate = None
            if ev[0] == 'up':
                nav_pos = (nav_pos - 1) % len(nav_indices)
            elif ev[0] == 'down':
                nav_pos = (nav_pos + 1) % len(nav_indices)
            elif ev[0] == 'del':
                val = items[cur][1]
                if val and val.startswith('path:'):
                    save_extra_paths(proj_folder, [p for p in paths if p != val[5:]])
                    redraw = True
            elif ev[0] == 'enter':
                activate = items[cur][1]
            elif ev[0] == 'esc':
                return

            if activate == 'back':
                return
            elif activate == 'add':
                new_path = text_input("Enter Windows path to add (e.g. C:\\tools\\bin):")
                if new_path and new_path not in paths:
                    paths.append(new_path)
                    save_extra_paths(proj_folder, paths)
                redraw = True


def launch_options_menu(project_name, default_effort='', default_model=''):
    """Returns (effort: str, model: str), empty = global default.
    Returns None on ESC (caller should go back instead of launching).
    default_effort/default_model preselect the fields when valid."""
    effort_idx = EFFORTS.index(default_effort) if default_effort in EFFORTS else 0
    model_idx  = MODELS.index(default_model)  if default_model  in MODELS  else 0
    field = 0

    while True:
        e_sel = C_SEL if field == 0 else C_DIM
        m_sel = C_SEL if field == 1 else C_DIM
        frame = [
            render.header('CLAUDECTL', project_name, 'LAUNCH OPTIONS'),
            '',
            render.hline(),
            f"  {e_sel}{'▸' if field == 0 else ' '}  Effort :  [ {EFFORT_LABELS[effort_idx]:<10} ]{C_RESET}   {C_DIM}← → cycle{C_RESET}",
            f"  {m_sel}{'▸' if field == 1 else ' '}  Model  :  [ {MODEL_LABELS[model_idx]:<15} ]{C_RESET}   {C_DIM}← → cycle{C_RESET}",
            render.hline(),
            '',
            render.hint_bar("↑↓ switch field   ← → cycle   ENTER launch   ESC back"),
        ]
        render.render_frame(frame)

        ev = wait_event()
        if ev[0] in ('up', 'down'):
            field = (field + 1) % 2
        elif ev[0] in ('left', 'right'):
            step = -1 if ev[0] == 'left' else 1
            if field == 0: effort_idx = (effort_idx + step) % len(EFFORTS)
            else:           model_idx  = (model_idx  + step) % len(MODELS)
        elif ev[0] == 'enter':
            return EFFORTS[effort_idx], MODELS[model_idx]
        elif ev[0] == 'esc':
            return None
