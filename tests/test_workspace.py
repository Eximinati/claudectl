import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Sandbox, make_jsonl, run_flow, ESC

from claude_sessions import workspace, config


FIXED_SHA = 'a' * 40


def _stub_git(monkeypatch, sha=FIXED_SHA):
    monkeypatch.setattr(workspace, '_git_head', lambda p: (sha, sha[:7], 'main'))


def _seed_project(sb, monkeypatch, n_sessions=2, document_mcp=True):
    actual, enc, folder, sids = sb.add_project('repo', n_sessions=n_sessions)
    # README first, then CLAUDE.md → CLAUDE.md is the newer file (no conflict)
    with open(os.path.join(actual, 'README.md'), 'w', encoding='utf-8') as f:
        f.write('# repo\n\nhello\n')
    with open(os.path.join(actual, 'CLAUDE.md'), 'w', encoding='utf-8') as f:
        f.write('# repo\n\n## Project context\n')
    if document_mcp:
        # harness stubs mcp_servers = [('TestMCP','ok')]; document it in global md
        with open(config.global_claude_md, 'w', encoding='utf-8') as f:
            f.write('# Global\n<!-- MCP:TestMCP:START -->\n## MCP: TestMCP\n'
                    '- `do_thing` does a thing\n<!-- MCP:TestMCP:END -->\n')
    return actual, enc, folder, sids


# ── pure helpers ─────────────────────────────────────────────

def test_manifest_roundtrip(tmp_path):
    m = workspace._empty_manifest()
    m['repo']['head_sha'] = 'deadbeef'
    assert workspace.save_manifest(str(tmp_path), m)
    got = workspace.load_manifest(str(tmp_path))
    assert got['repo']['head_sha'] == 'deadbeef'
    assert got['schema_version'] == workspace.SCHEMA_VERSION


def test_migrate_fills_and_preserves():
    old = {'schema_version': 0, 'repo': {'head_sha': 'x'}, 'custom_future_key': 42}
    m = workspace._migrate(old)
    assert m['schema_version'] == workspace.SCHEMA_VERSION
    assert m['repo']['head_sha'] == 'x'           # kept
    assert m['repo']['branch'] == ''              # filled
    assert 'file_hashes' in m and 'operations' in m
    assert m['custom_future_key'] == 42           # unknown key preserved


def test_sha256_stable(tmp_path):
    p = tmp_path / 'f.txt'
    p.write_text('abc', encoding='utf-8')
    h1 = workspace._sha256_file(str(p))
    h2 = workspace._sha256_file(str(p))
    assert h1 and h1 == h2
    p.write_text('abcd', encoding='utf-8')
    assert workspace._sha256_file(str(p)) != h1


def test_count_tools():
    md = "## MCP: x\n| Tool | Desc |\n|---|---|\n| a | x |\n| b | y |\n"
    assert workspace._count_tools(md) == 2


# ── status evaluation ────────────────────────────────────────

def test_scaffold_makes_fresh(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    _stub_git(monkeypatch)
    actual, enc, folder, sids = _seed_project(sb, monkeypatch)
    workspace.update_manifest(actual, folder, 'scaffold')

    m, live, checks, score, safe = workspace.compute_status(actual, folder)
    states = {c['name']: c['state'] for c in checks}
    assert safe is True
    assert score >= 80, states
    assert states['claude_md'] == 'fresh'
    assert states['claude_md_fresh'] == 'fresh'
    assert states['mcp_docs'] == 'fresh'
    assert m['sessions']['analyzed_count'] == 2


def test_readme_change_makes_stale(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    _stub_git(monkeypatch)
    actual, enc, folder, sids = _seed_project(sb, monkeypatch)
    workspace.update_manifest(actual, folder, 'scaffold')
    _, _, _, fresh_score, _ = workspace.compute_status(actual, folder)

    with open(os.path.join(actual, 'README.md'), 'w', encoding='utf-8') as f:
        f.write('# repo\n\nCHANGED CONTENT\n')

    _, _, checks, score, safe = workspace.compute_status(actual, folder)
    states = {c['name']: c['state'] for c in checks}
    assert states['claude_md_fresh'] == 'stale'
    assert score < fresh_score
    assert safe is True   # stale ≠ unsafe


def test_repo_moved_makes_stale(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    _stub_git(monkeypatch, FIXED_SHA)
    actual, enc, folder, sids = _seed_project(sb, monkeypatch)
    workspace.update_manifest(actual, folder, 'scaffold')

    _stub_git(monkeypatch, 'b' * 40)   # HEAD moved
    _, _, checks, score, safe = workspace.compute_status(actual, folder)
    states = {c['name']: c['state'] for c in checks}
    assert states['repo'] == 'stale'
    assert states['claude_md_fresh'] == 'stale'


def test_new_session_makes_stale(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    _stub_git(monkeypatch)
    actual, enc, folder, sids = _seed_project(sb, monkeypatch, n_sessions=2)
    workspace.update_manifest(actual, folder, 'scaffold')

    make_jsonl(os.path.join(folder, 'bbbb0000-0000-0000-0000-000000000099.jsonl'))
    from claude_sessions import sessions as _s
    _s._info_cache.clear()

    _, _, checks, _, _ = workspace.compute_status(actual, folder)
    states = {c['name']: c['state'] for c in checks}
    assert states['sessions'] == 'stale'


def test_corrupt_manifest_invalid_not_safe(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    _stub_git(monkeypatch)
    actual, enc, folder, sids = _seed_project(sb, monkeypatch)
    d = os.path.join(actual, workspace.MANIFEST_DIR)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, workspace.MANIFEST_NAME), 'w', encoding='utf-8') as f:
        f.write('{ not valid json')

    m, _, checks, score, safe = workspace.compute_status(actual, folder)
    states = {c['name']: c['state'] for c in checks}
    assert states['manifest'] == 'invalid'
    assert safe is False
    # display must not have healed the corrupt file
    raw = open(os.path.join(d, workspace.MANIFEST_NAME), encoding='utf-8').read()
    assert raw == '{ not valid json'


def test_print_status_output(monkeypatch, tmp_path, capsys):
    sb = Sandbox(monkeypatch, tmp_path)
    _stub_git(monkeypatch)
    actual, enc, folder, sids = _seed_project(sb, monkeypatch)
    workspace.update_manifest(actual, folder, 'scaffold')

    workspace.print_workspace_status(actual, folder)
    out = capsys.readouterr().out
    for needle in ('Workspace Status', 'Repo HEAD', 'Sessions analyzed',
                   'MCP servers', 'CLAUDE.md status', 'Safe to launch',
                   'freshness score'):
        assert needle in out, needle


def test_status_screen_renders_and_exits(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    _stub_git(monkeypatch)
    actual, enc, folder, sids = _seed_project(sb, monkeypatch)
    workspace.update_manifest(actual, folder, 'scaffold')
    _res, cap, _ = run_flow(monkeypatch, ESC, workspace.workspace_status_screen,
                            actual, folder)
    assert 'WORKSPACE' in cap.plain
    assert 'Safe to launch' in cap.plain


def test_update_is_nonfatal_without_project(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    _stub_git(monkeypatch)
    # no project_path, no proj_folder → must not raise, returns None or dict
    res = workspace.update_manifest('', None, 'launch', choice='new')
    assert res is None or isinstance(res, dict)
