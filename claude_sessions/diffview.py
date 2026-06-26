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


def show_if_changed(old, new, title):
    """Show a diff only when there is a prior version to compare against."""
    if not (old or '').strip():
        return                       # first creation — nothing to diff
    if (old or '') == (new or ''):
        return
    try:
        show(old, new, title)
    except Exception:
        _c.log.exception('diff show failed')


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


def record_and_show(project_path, proj_folder, key, old, new):
    """Snapshot the old version, then show the diff if anything changed."""
    title = TITLES.get(key, key)
    try:
        record(project_path, proj_folder, key, old, new)
    except Exception:
        _c.log.exception('diff snapshot failed')
    show_if_changed(old, new, title)
