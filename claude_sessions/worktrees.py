"""The worktree board: which agent is working where, and on what.

Every tool in the parallel-agent category — Conductor, Crystal/Nimbalyst, Claude
Squad, ccpm, vibe-kanban — is built on the same idea: run several agents at once
in isolated git worktrees, then review and merge the diffs in one place.
claudectl could already *launch* into a worktree (`-w`) and had no idea what
happened next.

WHAT THIS IS NOT
----------------
Not a clone of Conductor. About 70% of the parts were already here — worktree
launch, background jobs with approval gates, `diffview`, multi-account, and the
semantic memory — and what was missing is only the view that joins them up.

The join is the interesting bit and it is one nobody else can make: claudectl
knows which SESSION is in which worktree, because it knows both. A session's
transcript records its `cwd`; a worktree is a path. Match them and the board can
say "the refactor is running in ../wt-refactor, it has touched 9 files, and it
last spoke 40 seconds ago" — which is the question you actually have when three
agents are running.

And the differentiator none of the others have: every one of those sessions
reads the same semantic memory, so they are not each rediscovering the codebase.

COST
----
`git worktree list --porcelain` per project and a stat of each session's
transcript. No transcript parsing in the listing path — that happens only when
you open one.
"""

import os
import subprocess
import time

from . import config as _c

#: a session whose transcript moved inside this window is "live" in its worktree
LIVE_WINDOW = 600


def _git(args, cwd, timeout=15):
    try:
        r = subprocess.run(['git'] + args, cwd=cwd, capture_output=True,
                           text=True, timeout=timeout)
    except Exception:
        return None
    return r.stdout if r.returncode == 0 else None


def list_worktrees(project_path):
    """[{path, branch, head, bare, detached, main}] for a repo, or []."""
    out = _git(['worktree', 'list', '--porcelain'], project_path)
    if not out:
        return []
    trees, cur = [], {}
    for line in out.splitlines():
        if not line.strip():
            if cur:
                trees.append(cur)
                cur = {}
            continue
        key, _, val = line.partition(' ')
        if key == 'worktree':
            cur = {'path': os.path.normpath(val), 'branch': '', 'head': '',
                   'detached': False, 'bare': False}
        elif key == 'HEAD':
            cur['head'] = val[:8]
        elif key == 'branch':
            cur['branch'] = val.rsplit('/', 1)[-1]
        elif key == 'detached':
            cur['detached'] = True
        elif key == 'bare':
            cur['bare'] = True
    if cur:
        trees.append(cur)
    # the first entry is always the main working tree
    for i, t in enumerate(trees):
        t['main'] = (i == 0)
    return trees


def dirty(path):
    """(changed_files, insertions_estimate) for uncommitted work, or (0, 0)."""
    out = _git(['status', '--porcelain'], path)
    if out is None:
        return 0, 0
    files = [l for l in out.splitlines() if l.strip()]
    return len(files), 0


def ahead_behind(path, base='HEAD@{upstream}'):
    """(ahead, behind) against the upstream, or (0, 0) when there is none."""
    out = _git(['rev-list', '--left-right', '--count', f'{base}...HEAD'], path)
    if not out:
        return 0, 0
    try:
        behind, ahead = out.split()[:2]
        return int(ahead), int(behind)
    except Exception:
        return 0, 0


def _sessions_by_cwd(project_path, proj_folder):
    """{normalised cwd -> newest session touching it}.

    The join that makes this a BOARD rather than a list of directories. A
    transcript records the cwd it ran in, so a worktree path resolves to the
    session working in it — which is the thing you want to know and the thing
    only a tool that owns both halves can answer.
    """
    from .sessions import account_folders_for, scan_sessions
    from .stats import get_session_stats_cached
    out = {}
    try:
        enc = os.path.basename(proj_folder or '')
        folders = account_folders_for(enc) if enc else []
    except Exception:
        folders = []
    for acct, folder in folders:
        try:
            rows = scan_sessions(folder)
        except Exception:
            continue
        for mtime, sid, _preview, count in rows:
            jsonl = os.path.join(folder, f'{sid}.jsonl')
            try:
                st = get_session_stats_cached(jsonl)
            except Exception:
                continue
            cwd = (st.get('cwd') or '').strip()
            if not cwd:
                continue
            key = os.path.normcase(os.path.normpath(cwd))
            prev = out.get(key)
            if prev and prev['mtime'] >= mtime:
                continue
            out[key] = {'sid': sid, 'mtime': mtime, 'account': acct,
                        'msgs': count, 'branch': st.get('branch', ''),
                        'title': st.get('title', ''), 'cfgdir':
                            os.path.dirname(os.path.dirname(folder))}
    return out


def board(project_path, proj_folder=None):
    """Everything the board renders, in one call.

    [{path, name, branch, head, main, dirty, ahead, behind, session}] where
    `session` is the newest session running in that worktree, or None.
    """
    trees = list_worktrees(project_path)
    if not trees:
        return {'worktrees': [], 'repo': False}
    by_cwd = _sessions_by_cwd(project_path, proj_folder)
    now = time.time()
    rows = []
    for t in trees:
        if t.get('bare'):
            continue
        key = os.path.normcase(os.path.normpath(t['path']))
        s = by_cwd.get(key)
        n_dirty, _ = dirty(t['path'])
        ahead, behind = ahead_behind(t['path'])
        if s:
            age = now - s['mtime']
            s = dict(s, age=int(age), live=age < LIVE_WINDOW)
        rows.append({
            'path': t['path'],
            'name': os.path.basename(t['path']) or t['path'],
            'branch': t['branch'] or ('detached @ ' + t['head']),
            'head': t['head'], 'main': t['main'],
            'dirty': n_dirty, 'ahead': ahead, 'behind': behind,
            'session': s,
        })
    # live first, then dirtiest, then the main tree last — the board is for
    # finding the one that needs you, not for browsing directories
    rows.sort(key=lambda r: (r['main'],
                             not (r['session'] or {}).get('live'),
                             -r['dirty']))
    return {'worktrees': rows, 'repo': True}


def diff(path, staged=False):
    """The uncommitted diff of one worktree, for review before merging."""
    args = ['diff', '--stat=200', '--patch']
    if staged:
        args.insert(1, '--cached')
    return _git(args, path) or ''


def merge_into_main(project_path, branch):
    """Merge a worktree's branch into the current branch of the main tree.

    Gated by the caller through `diffview.confirm` — the same approval path
    every other write in claudectl goes through — so nothing here decides on
    its own that a merge is a good idea. `--no-ff` keeps the parallel work
    legible as its own line in the history, which is the whole reason it was
    run in a separate worktree.
    """
    out = _git(['merge', '--no-ff', '--no-edit', branch], project_path, timeout=60)
    if out is None:
        return False, f'merge of {branch} failed (conflicts, or not a repo)'
    return True, out.strip()[:400] or f'Merged {branch}'


def remove(path, force=False):
    """Drop a worktree. Refuses to discard uncommitted work unless forced."""
    n_dirty, _ = dirty(path)
    if n_dirty and not force:
        return False, f'{n_dirty} uncommitted change(s) — nothing removed'
    args = ['worktree', 'remove']
    if force:
        args.append('--force')
    out = _git(args + [path], os.path.dirname(path) or path, timeout=30)
    if out is None:
        return False, 'git refused to remove that worktree'
    return True, f'Removed {os.path.basename(path)}'
