"""Repo discovery for a project that is a PARENT of repos.

The Worktrees tab reported "not a git repository" for D:/repos and D:/Lavoro —
directories that hold 15 and 5 repos respectively. The cause was not in the
board: `find_git_repos` tested `isdir('.git')`, so every submodule and linked
worktree was invisible, and it stopped descending as soon as a child turned out
to be a repo, so a repo's own submodules were unreachable.

The tests below are filesystem-only. None of them needs the git binary, which is
deliberate: the classification that fixes the bug reads ONE line out of a `.git`
file, and a test that shelled out would be testing git rather than that.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_sessions import config as cfg
from claude_sessions import repos


def _repo(path):
    os.makedirs(os.path.join(path, '.git'), exist_ok=True)
    with open(os.path.join(path, '.git', 'HEAD'), 'w', encoding='utf-8') as f:
        f.write('ref: refs/heads/main\n')
    return path


def _gitfile(path, target):
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, '.git'), 'w', encoding='utf-8') as f:
        f.write(f'gitdir: {target}\n')
    return path


def _isolate(monkeypatch, tmp_path):
    """Never touch the real cache in ~/.claude."""
    monkeypatch.setattr(cfg, 'config_dir', str(tmp_path / 'cfg'))
    os.makedirs(str(tmp_path / 'cfg'), exist_ok=True)


# ── the classification that fixes the bug ─────────────────────

def test_a_dot_git_file_is_a_repo_not_a_directory(tmp_path):
    """The headline defect. A submodule stores `.git` as a FILE, so an
    `isdir` test made all 7 of IKM.Workspace's submodules invisible."""
    sub = _gitfile(str(tmp_path / 'sub'), '../.git/modules/sub')
    assert repos.classify(sub) == 'submodule'
    assert sub in repos.find_git_repos(str(tmp_path))


def test_a_linked_worktree_is_not_counted_as_a_repo(tmp_path):
    """D:/Claude keeps ten of them under .claude/worktrees. Counting them as
    repos would triple that project's repo list with copies of itself —
    worktrees come from `git worktree list`, never from the walk."""
    wt = _gitfile(str(tmp_path / 'wt'), 'D:/proj/.git/worktrees/wt')
    assert repos.classify(wt) == 'worktree'
    assert wt not in repos.find_git_repos(str(tmp_path))


def test_the_two_are_told_apart_without_running_git(tmp_path, monkeypatch):
    """One line of the `.git` file decides it: .git/modules vs .git/worktrees."""
    monkeypatch.setattr(repos, '_git', lambda *a, **k: (_ for _ in ()).throw(
        AssertionError('classification must not shell out')))
    _gitfile(str(tmp_path / 'a'), '../.git/modules/a')
    _gitfile(str(tmp_path / 'b'), 'X:/p/.git/worktrees/b')
    assert repos.classify(str(tmp_path / 'a')) == 'submodule'
    assert repos.classify(str(tmp_path / 'b')) == 'worktree'


def test_discovery_keeps_descending_into_a_repo(tmp_path):
    """The second defect: `elif max_depth > 1` meant a child that WAS a repo
    was never opened, so its submodules could not be reached."""
    parent = _repo(str(tmp_path / 'parent'))
    child = _gitfile(str(tmp_path / 'parent' / 'child'), '../.git/modules/child')
    found = repos.find_git_repos(str(tmp_path))
    assert parent in found and child in found, found


def test_depth_is_honoured_and_noise_directories_are_pruned(tmp_path):
    """Reuses connections.SKIP_DIRS rather than inventing a second list."""
    deep = _repo(str(tmp_path / 'a' / 'b' / 'c' / 'deep'))
    too_deep = _repo(str(tmp_path / 'a' / 'b' / 'c' / 'd' / 'e' / 'far'))
    vendored = _repo(str(tmp_path / 'node_modules' / 'pkg'))
    found = repos.find_git_repos(str(tmp_path), max_depth=4)
    assert deep in found
    assert too_deep not in found
    assert vendored not in found


def test_owner_of_walks_up_and_gives_up(tmp_path):
    root = _repo(str(tmp_path / 'r'))
    deep = os.path.join(root, 'x', 'y')
    os.makedirs(deep, exist_ok=True)
    assert repos.owner_of(deep) == root
    outside = str(tmp_path / 'nothing')
    os.makedirs(outside, exist_ok=True)
    assert repos.owner_of(outside) == ''


def test_the_branch_is_read_from_disk_not_from_git(tmp_path, monkeypatch):
    """The branch must never be cached, so it can never be stale — and reading
    .git/HEAD is cheaper than the cache lookup would be anyway."""
    monkeypatch.setattr(repos, '_git', lambda *a, **k: (_ for _ in ()).throw(
        AssertionError('the branch must not cost a subprocess')))
    r = _repo(str(tmp_path / 'r'))
    assert repos.head_branch(r) == 'main'
    with open(os.path.join(r, '.git', 'HEAD'), 'w', encoding='utf-8') as f:
        f.write('ref: refs/heads/feature/nested/name\n')
    assert repos.head_branch(r) == 'feature/nested/name'
    with open(os.path.join(r, '.git', 'HEAD'), 'w', encoding='utf-8') as f:
        f.write('9f1c0de0e0f2ab\n')
    assert repos.head_branch(r) == ''      # detached


def test_a_submodules_branch_resolves_through_its_gitdir(tmp_path):
    """`.git` is a file, so HEAD lives somewhere else entirely."""
    real = str(tmp_path / 'parent' / '.git' / 'modules' / 'sub')
    os.makedirs(real, exist_ok=True)
    with open(os.path.join(real, 'HEAD'), 'w', encoding='utf-8') as f:
        f.write('ref: refs/heads/develop\n')
    sub = _gitfile(str(tmp_path / 'parent' / 'sub'), '../.git/modules/sub')
    assert repos.head_branch(sub) == 'develop'


# ── the cache the statusline runs on ──────────────────────────

def test_cached_state_never_spawns_git(tmp_path, monkeypatch):
    """The statusline's whole contract. It runs on every conversation turn and
    `git status` costs 60-270ms; refresh=False must be an absolute guarantee,
    not a best effort."""
    _isolate(monkeypatch, tmp_path)
    r = _repo(str(tmp_path / 'r'))
    monkeypatch.setattr(repos, '_git', lambda *a, **k: (_ for _ in ()).throw(
        AssertionError('refresh=False must not shell out')))
    st = repos.state(r, refresh=False)
    assert st['branch'] == 'main' and st['stale'] is True
    assert st['dirty'] == 0


def test_a_refresh_is_cached_and_then_reused(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    r = _repo(str(tmp_path / 'r'))
    calls = []

    def fake(args, cwd, timeout=15):
        calls.append(args)
        return '# branch.oid abc1234567\n# branch.ab +2 -1\nfoo\nbar\n'

    monkeypatch.setattr(repos, '_git', fake)
    first = repos.state(r)
    assert (first['dirty'], first['ahead'], first['behind']) == (2, 2, 1)
    assert first['stale'] is False
    second = repos.state(r)
    assert len(calls) == 1, 'the second read must come from cache'
    assert second['dirty'] == 2


def test_the_cache_is_invalidated_when_the_index_moves(tmp_path, monkeypatch):
    """A commit or a checkout changes ahead/behind, and both touch .git/index.
    A plain file edit does not — which is why `dirty` is TTL-bounded instead."""
    _isolate(monkeypatch, tmp_path)
    r = _repo(str(tmp_path / 'r'))
    idx = os.path.join(r, '.git', 'index')
    open(idx, 'w').close()
    n = [0]

    def fake(args, cwd, timeout=15):
        n[0] += 1
        return f'# branch.oid abc1234567\n' + 'x\n' * n[0]

    monkeypatch.setattr(repos, '_git', fake)
    assert repos.state(r)['dirty'] == 1
    assert repos.state(r)['dirty'] == 1              # cached
    os.utime(idx, (0, 0))                            # a commit landed
    assert repos.state(r)['dirty'] == 2, 'index moved — must re-read'


def test_remember_takes_measurements_rather_than_paths(tmp_path, monkeypatch):
    """The board has just run git for every repo. Re-running it to populate the
    cache would double the cost of opening the tab."""
    _isolate(monkeypatch, tmp_path)
    r = _repo(str(tmp_path / 'r'))
    monkeypatch.setattr(repos, '_git', lambda *a, **k: (_ for _ in ()).throw(
        AssertionError('remember must not re-measure')))
    repos.remember({r: {'dirty': 4, 'ahead': 1, 'behind': 0, 'head': 'abc'}})
    assert repos.state(r, refresh=False)['dirty'] == 4


def test_a_torn_cache_file_is_survivable(tmp_path, monkeypatch):
    """It is written by a process Claude Code cancels at will."""
    _isolate(monkeypatch, tmp_path)
    with open(repos._cache_file(), 'w', encoding='utf-8') as f:
        f.write('{"repos": {"a": ')       # truncated mid-write
    r = _repo(str(tmp_path / 'r'))
    assert repos.state(r, refresh=False)['branch'] == 'main'


def test_summary_rolls_up_a_parent_of_repos(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    a = _repo(str(tmp_path / 'a'))
    _repo(str(tmp_path / 'b'))
    repos.remember({a: {'dirty': 3, 'ahead': 0, 'behind': 0, 'head': ''}})
    s = repos.summary(str(tmp_path), refresh=False)
    assert s['repos'] == 2 and s['dirty'] == 1
