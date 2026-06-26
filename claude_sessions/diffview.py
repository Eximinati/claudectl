"""Git-like colored diffs for generated/updated files.

Shows what changed (old → new) after CLAUDE.md / system-prompt / global MCP
updates, and snapshots the previous version under <project>/.claudectl/snapshots
(fallback ~/.claude/projects/<encoded>/.claudectl/snapshots) so the last change
can be reviewed later from the workspace screen. All helpers are best-effort —
a diff/snapshot failure never blocks the operation that triggered it.
"""

import os
import json
import time
import difflib

from . import config as _c
from . import render

_SNAP_SUBDIR = os.path.join('.claudectl', 'snapshots')
_INDEX = 'index.json'
TITLES = {'claude_md': 'CLAUDE.md', 'system_prompt': 'system prompt',
          'global_claude_md': 'global CLAUDE.md'}


# ── pure diff helpers ────────────────────────────────────────

def unified(old, new, label='file'):
    return list(difflib.unified_diff(
        (old or '').splitlines(), (new or '').splitlines(),
        fromfile=f'{label} (before)', tofile=f'{label} (after)', lineterm=''))


def stat(old, new):
    added = removed = 0
    for ln in unified(old, new):
        if ln.startswith('+') and not ln.startswith('+++'):
            added += 1
        elif ln.startswith('-') and not ln.startswith('---'):
            removed += 1
    return added, removed


def colorize(diff_lines):
    out = []
    for ln in diff_lines:
        if ln.startswith('+++') or ln.startswith('---'):
            out.append(f"{_c.C_DIM}{ln}{_c.C_RESET}")
        elif ln.startswith('@@'):
            out.append(f"{_c.C_ACCENT}{ln}{_c.C_RESET}")
        elif ln.startswith('+'):
            out.append(f"{_c.C_OK}{ln}{_c.C_RESET}")
        elif ln.startswith('-'):
            out.append(f"{_c.C_ERR}{ln}{_c.C_RESET}")
        else:
            out.append(ln)
    return out


# ── display ──────────────────────────────────────────────────

def show(old, new, title):
    """Open a colored unified diff in the pager. ESC/ENTER dismiss."""
    from .ui import pager
    label = title
    if (old or '') == (new or ''):
        pager(('CLAUDECTL', title, 'DIFF'),
              [f"{_c.C_DIM}(no changes){_c.C_RESET}"], hint='ESC back')
        return
    added, removed = stat(old, new)
    header = [f"{_c.C_OK}+{added}{_c.C_RESET}  {_c.C_ERR}-{removed}{_c.C_RESET}"
              f"   {_c.C_DIM}{label}{_c.C_RESET}"]
    body = colorize(unified(old, new, label))
    pager(('CLAUDECTL', title, 'DIFF'), body, header_lines=header, hint='ESC back')


def confirm(old, new, title):
    """Preview a proposed change BEFORE writing: shows the colored diff
    (old → new) so the user approves/rejects based on what changed. `f`
    toggles between the diff and the full proposed content. ENTER approve,
    ESC reject. Returns True (approve) / False (reject)."""
    from .ui import flush_input, wait_event
    has_old = bool((old or '').strip()) and old != new
    added, removed = stat(old, new) if has_old else (0, 0)
    diff_body = colorize(unified(old, new, title)) if has_old else []
    full_body = (new or '').splitlines()
    mode_diff = has_old

    flush_input()
    top = 0
    pending = None
    while True:
        body = diff_body if mode_diff else full_body
        page = max(4, render.frame_height() - 7)
        top = max(0, min(top, max(0, len(body) - page)))
        at_end = top + page >= len(body)
        if has_old:
            hdr = (f"{_c.C_OK}+{added}{_c.C_RESET}  {_c.C_ERR}-{removed}{_c.C_RESET}   "
                   f"{_c.C_DIM}{title} — {'diff' if mode_diff else 'full proposed'}{_c.C_RESET}")
        else:
            hdr = f"{_c.C_DIM}{title} — new content (nothing to compare){_c.C_RESET}"
        frame = [render.header('CLAUDECTL', title, 'REVIEW'), '', '  ' + hdr, render.hline()]
        for ln in body[top:top + page]:
            frame.append(render.fit('  ' + ln, render.content_width()))
        frame.append('')
        keys = [('↑↓', 'scroll'), ('←→/SPACE', 'page')]
        if has_old:
            keys.append(('f', 'full' if mode_diff else 'diff'))
        keys += [('ENTER', 'approve & write'), ('ESC', 'reject')]
        frame.append(render.hint_keys(
            keys, prefix=f"{min(top + page, len(body))}/{len(body)}"
                         + ("  (end)" if at_end else "")))
        render.render_frame(frame)

        ev = pending if pending else wait_event()
        pending = None
        if ev[0] == 'up':
            top -= 1
        elif ev[0] == 'down':
            top += 1
        elif ev[0] == 'left':
            top -= page
        elif ev[0] == 'right' or (ev[0] == 'char' and ev[1] == ' '):
            top += page
        elif ev[0] == 'char' and ev[1] == 'f' and has_old:
            mode_diff = not mode_diff
            top = 0
        elif ev[0] == 'enter':
            return True
        elif ev[0] == 'esc':
            return False


# ── snapshot store ───────────────────────────────────────────

def _candidate_dirs(project_path, proj_folder):
    out = []
    if project_path:
        out.append(os.path.join(project_path, _SNAP_SUBDIR))
    if proj_folder:
        out.append(os.path.join(proj_folder, _SNAP_SUBDIR))
    return out


def _read_index(d):
    try:
        with open(os.path.join(d, _INDEX), encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def record(project_path, proj_folder, key, old, new):
    """Persist the pre-update version (<key>.prev) + an index entry. Best-effort."""
    added, removed = stat(old, new)
    for d in _candidate_dirs(project_path, proj_folder):
        try:
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, f'{key}.prev'), 'w', encoding='utf-8') as f:
                f.write(old or '')
            idx = _read_index(d)
            idx.append({'ts': time.time(), 'key': key,
                        'added': added, 'removed': removed})
            with open(os.path.join(d, _INDEX), 'w', encoding='utf-8') as f:
                json.dump(idx[-20:], f, indent=2)
            return True
        except Exception:
            continue
    return False


def load_prev(project_path, proj_folder, key):
    for d in _candidate_dirs(project_path, proj_folder):
        p = os.path.join(d, f'{key}.prev')
        if os.path.isfile(p):
            try:
                return open(p, encoding='utf-8', errors='ignore').read()
            except Exception:
                return ''
    return ''


def last_change(project_path, proj_folder, key):
    """Latest index entry for `key`, or None."""
    for d in _candidate_dirs(project_path, proj_folder):
        idx = _read_index(d)
        if idx:
            for e in reversed(idx):
                if e.get('key') == key:
                    return e
    return None


