import os
import sys
import msvcrt
import time
import ctypes

from .config import W, EFFORTS, EFFORT_LABELS, MODELS, MODEL_LABELS
from .config import C_RESET, C_TITLE, C_SEL, C_DIM, C_SRCH, C_BOLD
from .sessions import load_extra_paths, save_extra_paths


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

_enable_vt_mode()


def _cls():
    """Clear screen — ANSI (instant, no subprocess) if VT enabled, else fallback."""
    if _VT_ENABLED:
        sys.stdout.write('\x1b[2J\x1b[H')
        sys.stdout.flush()
    else:
        os.system('cls')


# ── UI primitives ────────────────────────────────────────────

def text_input(prompt, default=''):
    buf = list(default)
    while True:
        _cls()
        print(f"\n  {C_TITLE}{prompt}{C_RESET}")
        print(f"\n  {C_SEL}>{C_RESET} {''.join(buf)}_")
        print(f"\n  {C_DIM}ENTER confirm   ESC cancel   BACKSPACE delete{C_RESET}")
        raw = msvcrt.getwch()
        if raw in ('\r', '\n'):
            return ''.join(buf).strip()
        elif raw == '\x1b':
            return None
        elif raw == '\x08':
            if buf: buf.pop()
        elif raw in ('\x00', '\xe0'):
            msvcrt.getwch()
        elif raw >= ' ':
            buf.append(raw)


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

    def _draw(current_footer):
        disp = _filtered()
        ni   = _nav_idx(disp)
        if not ni:
            return
        pos = min(nav_pos, len(ni) - 1)
        cur = ni[pos]

        _cls()
        print(f"\n  {C_TITLE}{C_BOLD}{title}{C_RESET}\n")

        # Search bar — always visible
        if search_str:
            print(f"  {C_SRCH}[ {search_str}▌ ]{C_RESET}\n")
        else:
            print(f"  {C_DIM}[ search... ]{C_RESET}\n")

        for i, (label, val) in enumerate(disp):
            if val is None:
                print(f"  {C_DIM}{label}{C_RESET}")
            elif i == cur:
                print(f"  {C_SEL}>{C_RESET} {label}")
            else:
                print(f"    {label}")

        if search_str:
            hint = f"  {C_DIM}↑↓ navigate   ENTER select   BACKSPACE delete   ESC clear{C_RESET}"
        else:
            hint = f"  {C_DIM}↑↓ navigate   ENTER select   type to search   ESC back{C_RESET}"
        print(f"\n{hint}")
        if current_footer:
            print(f"\n{current_footer}")

    current_footer = footer_fn() if footer_fn else footer
    _draw(current_footer)
    _last_footer  = current_footer
    _footer_done  = False   # True after first live update — stop polling

    while True:
        if not msvcrt.kbhit():
            if footer_fn and not _footer_done:
                current = footer_fn()
                if current != _last_footer:
                    _last_footer = current
                    _footer_done = True   # update exactly once
                    if _VT_ENABLED:
                        _draw(_last_footer)
            time.sleep(0.1)
            continue

        key = ord(msvcrt.getch())

        if key == 224:
            k2   = ord(msvcrt.getch())
            disp = _filtered()
            ni   = _nav_idx(disp)
            if ni:
                if k2 == 72:   nav_pos = (nav_pos - 1) % len(ni)
                elif k2 == 80: nav_pos = (nav_pos + 1) % len(ni)
        elif key == 13:   # ENTER
            disp = _filtered()
            ni   = _nav_idx(disp)
            if ni:
                return disp[ni[min(nav_pos, len(ni) - 1)]][1]
            return None
        elif key == 27:   # ESC
            if search_str:
                search_str = ''
                nav_pos    = 0
            else:
                return None
        elif key == 8:    # BACKSPACE
            if search_str:
                search_str = search_str[:-1]
                nav_pos    = 0
        elif 32 <= key <= 126:
            search_str += chr(key)
            nav_pos    = 0

        _draw(_last_footer)


# ── feature menus ────────────────────────────────────────────

def paths_menu(proj_folder, project_name):
    while True:
        paths = load_extra_paths(proj_folder)
        items = [(f"{'─' * W}", None)]
        for p in paths:
            items.append((f"  {p}", f"path:{p}"))
        if not paths:
            items.append((f"  (no extra paths configured)", None))
        items += [(f"{'─' * W}", None), (f"  + Add new path", 'add'), (f"  Back", 'back')]

        nav_indices = [i for i, (_, v) in enumerate(items) if v is not None]
        nav_pos = 0
        redraw = False
        while not redraw:
            cur = nav_indices[nav_pos]
            _cls()
            print(f"\n  {C_TITLE}{C_BOLD}EXTRA PATHS  /  {project_name}{C_RESET}\n")
            for i, (label, val) in enumerate(items):
                if val is None:
                    print(f"  {C_DIM}{label}{C_RESET}")
                elif i == cur:
                    print(f"  {C_SEL}>{C_RESET} {label}")
                else:
                    print(f"    {label}")
            print(f"\n  {C_DIM}↑↓ navigate   ENTER select   DEL remove   ESC back{C_RESET}")
            key = ord(msvcrt.getch())
            if key == 224:
                k2 = ord(msvcrt.getch())
                if k2 == 72:   nav_pos = (nav_pos - 1) % len(nav_indices)
                elif k2 == 80: nav_pos = (nav_pos + 1) % len(nav_indices)
                elif k2 == 83:
                    val = items[cur][1]
                    if val and val.startswith('path:'):
                        save_extra_paths(proj_folder, [p for p in paths if p != val[5:]])
                        redraw = True
            elif key == 13:
                val = items[cur][1]
                if val == 'back':
                    return
                elif val == 'add':
                    new_path = text_input("Enter Windows path to add (e.g. C:\\tools\\bin):")
                    if new_path and new_path not in paths:
                        paths.append(new_path)
                        save_extra_paths(proj_folder, paths)
                    redraw = True
            elif key == 27:
                return


def launch_options_menu(project_name):
    """Returns (effort: str, model: str). Empty = use global default."""
    effort_idx = 0
    model_idx  = 0
    field = 0

    while True:
        _cls()
        print(f"\n  {C_TITLE}{C_BOLD}LAUNCH OPTIONS  /  {project_name}{C_RESET}")
        print(f"\n  {C_DIM}{'─' * W}{C_RESET}")
        e_sel = C_SEL if field == 0 else C_DIM
        m_sel = C_SEL if field == 1 else C_DIM
        print(f"  {e_sel}{'>' if field == 0 else ' '}  Effort :  [ {EFFORT_LABELS[effort_idx]:<10} ]{C_RESET}   {C_DIM}← → cycle{C_RESET}")
        print(f"  {m_sel}{'>' if field == 1 else ' '}  Model  :  [ {MODEL_LABELS[model_idx]:<15} ]{C_RESET}   {C_DIM}← → cycle{C_RESET}")
        print(f"  {C_DIM}{'─' * W}{C_RESET}")
        print(f"\n  {C_DIM}↑↓ switch field   ← → cycle   ENTER launch   ESC use defaults{C_RESET}")
        key = ord(msvcrt.getch())
        if key == 224:
            k2 = ord(msvcrt.getch())
            if k2 == 72:   field = (field - 1) % 2
            elif k2 == 80: field = (field + 1) % 2
            elif k2 == 75:
                if field == 0: effort_idx = (effort_idx - 1) % len(EFFORTS)
                else:           model_idx  = (model_idx  - 1) % len(MODELS)
            elif k2 == 77:
                if field == 0: effort_idx = (effort_idx + 1) % len(EFFORTS)
                else:           model_idx  = (model_idx  + 1) % len(MODELS)
        elif key == 13:
            return EFFORTS[effort_idx], MODELS[model_idx]
        elif key == 27:
            return '', ''
