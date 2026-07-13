import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Sandbox, make_jsonl
from claude_sessions import context_inject as ci
from claude_sessions.paths import encode_component


def test_account_name_for_matches_default(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    assert ci._account_name_for(sb.cfg) == 'default'


def test_find_sessions_across_accounts_reads_title(monkeypatch, tmp_path):
    # find_sessions_across_accounts uses the REAL encode_component (unlike
    # harness.add_project's simplified fake scheme), so build the project
    # folder directly with the real encoding.
    sb = Sandbox(monkeypatch, tmp_path)
    actual = str(tmp_path / 'work' / 'alpha')
    os.makedirs(actual, exist_ok=True)
    enc = encode_component(actual)
    folder = os.path.join(str(sb.projects), enc)
    os.makedirs(folder, exist_ok=True)
    sid = 'aaaa0000-0000-0000-0000-000000000000'
    make_jsonl(os.path.join(folder, f'{sid}.jsonl'), title='Fix the bug')

    found = ci.find_sessions_across_accounts(actual)
    assert len(found) == 1
    acct_name, found_folder, found_sid, mtime, preview, title = found[0]
    assert acct_name == 'default'
    assert found_folder == folder
    assert found_sid == sid
    assert title == 'Fix the bug'


def test_write_context_file_contains_transcript(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    actual, enc, folder, sids = sb.add_project('beta', n_sessions=1, title='Refactor auth')
    ctx_path, title = ci._write_context_file(actual, folder, sids[0], 'default')
    assert title == 'Refactor auth'
    assert os.path.isfile(ctx_path)
    text = open(ctx_path, encoding='utf-8').read()
    assert 'Refactor auth' in text
    assert 'account: default' in text
    assert 'hello world message' in text   # from make_jsonl's default preview text
