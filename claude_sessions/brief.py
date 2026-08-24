"""Project brief — instant, local (no Claude call) situational awareness:
  • work_suggestions: ranked next-steps from lessons, graph importance, health.
  • session_diff: what changed since the last session (git + session-log).
Both are token-frugal and automatic; surfaced in the memory hub.
"""

import os
import subprocess

from . import memory


def work_suggestions(project_path, proj_folder):
    """[(priority_str, text)] ranked next-steps. Pure local."""
    out = []
    mem = memory.load_memory(project_path, proj_folder)

    # 1. unresolved error_fix lessons → likely recurring pain
    fixes = [e for e in mem.get('entities', [])
             if e.get('type') == 'lesson' and e.get('kind') == 'error_fix'
             and e.get('status') in ('approved', 'pinned')]
    for l in fixes[:3]:
        out.append(('fix', f"recurring issue: {l.get('summary', l.get('name', ''))}"))

    # 2. pending lessons awaiting review
    try:
        from . import lessons
        pend = lessons.pending_sids(proj_folder, mem)
        if pend:
            out.append(('learn', f"{len(pend)} session(s) not yet learned — press L"))
    except Exception:
        pass

    # 3. most-connected modules (graph rank) → the project's backbone
    mods = {}
    for e in mem.get('entities', []):
        if e.get('type') == 'lesson':
            continue
        u = f"{e.get('repo')}/{e.get('module')}"
        mods[u] = max(mods.get(u, 0), e.get('rank', 0))
    top = sorted(mods.items(), key=lambda kv: -kv[1])[:3]
    for u, r in top:
        if r > 0:
            out.append(('core', f"central module: {u} (most-connected)"))

    # 4. open health issues
    try:
        from . import health
        for sev, msg, _hint in health.check_project(project_path, proj_folder):
            if sev == 'warn':
                out.append(('health', msg))
    except Exception:
        pass

    if not out:
        out.append(('info', 'no signals yet — build memory (m→b) and run a session'))
    return out


def _last_session_stamp(project_path):
    """ISO-ish date of the most recent session-log entry, or ''."""
    from .health import SESSION_LOG
    p = os.path.join(project_path, SESSION_LOG)
    if not os.path.isfile(p):
        return ''
    try:
        for line in reversed(open(p, encoding='utf-8', errors='ignore').read().splitlines()):
            if line.startswith('## '):
                # "## 2026-07-05 14:30 — <sid>"
                return line[3:].split('—')[0].strip().split()[0]
    except Exception:
        pass
    return ''


def _git_repos(project_path, proj_folder):
    """Every git repo for this project: the root if it's one, plus any nested
    repos (a workspace often holds several sub-project repos, none at the root)."""
    repos = []
    try:
        from . import connections
        # no `isdir('.git')` filter: _discover_repos already returns repos, and
        # re-testing for a .git DIRECTORY here dropped every submodule again
        for r in connections._discover_repos(os.path.abspath(project_path), proj_folder):
            if r not in repos:
                repos.append(r)
    except Exception:
        pass
    return repos


#: (key) -> (expires_at, result). Opening the Tools tab ran `git log` AND
#: `git status` in every repo of the project — twenty subprocesses on a
#: ten-repo workspace, every single click, for an answer that cannot
#: meaningfully change between two clicks a few seconds apart.
#:
#: A TTL rather than a filesystem signature, deliberately: `dirty` comes from
#: `git status`, and editing a file touches NOTHING under .git, so no signature
#: can see it — the same limitation repos.state already documents. The cache
#: lives in the process, so it is empty on every launch and a stale answer can
#: never outlive the app.
_DIFF_TTL = 90.0
_diff_cache = {}


def session_diff_rows(project_path, proj_folder, refresh=False):
    """Structured 'since last session': one row per repo that moved.

    {'repos': [{'label','path','commits':[...],'dirty':N}], 'since': str|None,
     'note': str}  — `note` is set INSTEAD of repos when there is nothing to
    show, so a caller never has to tell an empty list from a failure.

    This is the source; session_diff() below is a formatter over it. The GUI
    renders per repo and needs the counts, and re-deriving them by parsing the
    '▸ ' prefix off a formatted line is exactly the sort of round trip that
    breaks the first time the format changes.

    Cached for _DIFF_TTL seconds; pass refresh=True for the explicit reload.
    """
    import time
    key = (os.path.abspath(project_path), proj_folder or '')
    if not refresh:
        hit = _diff_cache.get(key)
        if hit and hit[0] > time.time():
            return hit[1]

    def _done(result):
        _diff_cache[key] = (time.time() + _DIFF_TTL, result)
        return result

    since = _last_session_stamp(project_path)
    repos = _git_repos(project_path, proj_folder)
    if not repos:
        return _done({'repos': [], 'since': since,
                      'note': '(no git repo here or in sub-projects — nothing to diff)'})

    from .repos import _git as _repo_git

    def _git(cwd, args):
        return (_repo_git(args, cwd, timeout=8) or '').strip()

    root = os.path.abspath(project_path)
    out = []
    for repo in repos:
        label = os.path.basename(repo.rstrip(os.sep)) or repo
        log_args = ['log', '--oneline', f'--since={since}'] if since else ['log', '--oneline', '-10']
        commits = _git(repo, log_args)
        dirty = _git(repo, ['status', '--porcelain'])
        if not commits and not dirty:
            continue                                 # quiet repo — skip
        out.append({
            'label': label if (len(repos) > 1 or repo != root) else '',
            'path': repo,
            'commits': commits.splitlines()[:10] if commits else [],
            'dirty': len(dirty.splitlines()) if dirty else 0,
        })
    if not out:
        return _done({'repos': [], 'since': since,
                      'note': f"(no changes since {since or 'the last session'})"})
    return _done({'repos': out, 'since': since, 'note': ''})


def session_diff(project_path, proj_folder):
    """'Since last session' as flat lines, for the TUI and the memory hub.
    A formatter over session_diff_rows — one place decides what 'moved' means."""
    data = session_diff_rows(project_path, proj_folder)
    if data['note']:
        return [data['note']]
    lines = []
    for r in data['repos']:
        lines.append(f"▸ {r['label']}" if r['label'] else 'commits:')
        lines += ['  ' + c for c in r['commits']]
        if r['dirty']:
            lines.append(f"  ({r['dirty']} uncommitted file(s))")
        lines.append('')
    return lines
