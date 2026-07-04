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


def session_diff(project_path, proj_folder):
    """'Since last session': git commits + changed-file stat since the last
    session-log stamp. Pure local; empty list if not a git repo."""
    since = _last_session_stamp(project_path)
    lines = []

    def _git(args):
        try:
            r = subprocess.run(['git', *args], cwd=project_path,
                               capture_output=True, text=True, timeout=8)
            return r.stdout.strip() if r.returncode == 0 else ''
        except Exception:
            return ''

    if not os.path.isdir(os.path.join(project_path, '.git')):
        return ['(not a git repo — nothing to diff)']

    log_args = ['log', '--oneline', '-15']
    if since:
        log_args = ['log', '--oneline', f'--since={since}']
    commits = _git(log_args)
    if commits:
        lines.append(f"commits since {since or 'recently'}:")
        lines += ['  ' + c for c in commits.splitlines()[:12]]
    stat = _git(['diff', '--stat', 'HEAD~5..HEAD'] if not since else
                ['diff', '--stat', f'@{{{since}}}..HEAD'])
    if stat:
        lines.append('')
        lines.append('files changed:')
        lines += ['  ' + s for s in stat.splitlines()[-8:]]
    dirty = _git(['status', '--porcelain'])
    if dirty:
        lines.append('')
        lines.append(f"uncommitted: {len(dirty.splitlines())} file(s) with changes")
    return lines or ['(no changes since last session)']
