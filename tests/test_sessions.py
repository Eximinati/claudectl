import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_sessions.sessions import (
    get_session_info, get_session_title, format_age,
    load_name, save_name, load_extra_paths, save_extra_paths,
)


def _write_jsonl(path, objs):
    with open(path, 'w', encoding='utf-8') as f:
        for o in objs:
            f.write(json.dumps(o) + '\n')


def test_get_session_info_missing_file():
    assert get_session_info(r'C:\nonexistent\nope.jsonl') == ('', 0)


def test_get_session_info_counts_and_preview(tmp_path):
    p = tmp_path / 's.jsonl'
    _write_jsonl(p, [
        {'role': 'user', 'content': 'first user message here'},
        {'role': 'assistant', 'content': 'reply'},
        {'role': 'user', 'content': 'second user message wins'},
    ])
    preview, count = get_session_info(str(p))
    assert count == 3
    assert preview.startswith('second user message')


def test_get_session_info_skips_bad_prefixes(tmp_path):
    p = tmp_path / 's.jsonl'
    _write_jsonl(p, [
        {'role': 'user', 'content': 'good message content'},
        {'role': 'user', 'content': '<system-tag> noise'},
    ])
    preview, count = get_session_info(str(p))
    assert preview.startswith('good message')


def test_get_session_info_nested_message_format(tmp_path):
    p = tmp_path / 's.jsonl'
    _write_jsonl(p, [
        {'message': {'role': 'user',
                     'content': [{'type': 'text', 'text': 'nested block text'}]}},
    ])
    preview, count = get_session_info(str(p))
    assert count == 1
    assert 'nested block text' in preview


def test_get_session_info_tolerates_garbage(tmp_path):
    p = tmp_path / 's.jsonl'
    p.write_text('not json at all\n{"role": "user", "content": "valid line"}\n',
                 encoding='utf-8')
    preview, count = get_session_info(str(p))
    assert count == 1


def test_get_session_title(tmp_path):
    p = tmp_path / 's.jsonl'
    _write_jsonl(p, [
        {'type': 'ai-title', 'title': 'My Session Title'},
        {'role': 'user', 'content': 'hello world message'},
    ])
    assert get_session_title(str(p)) == 'My Session Title'


def test_cache_invalidation_on_change(tmp_path):
    p = tmp_path / 's.jsonl'
    _write_jsonl(p, [{'role': 'user', 'content': 'message number one'}])
    _, count1 = get_session_info(str(p))
    _write_jsonl(p, [
        {'role': 'user', 'content': 'message number one'},
        {'role': 'assistant', 'content': 'two'},
    ])
    # force mtime difference on coarse filesystems
    os.utime(p, (os.path.getmtime(p) + 2, os.path.getmtime(p) + 2))
    _, count2 = get_session_info(str(p))
    assert count1 == 1 and count2 == 2


def test_format_age():
    import time
    assert format_age(time.time()).strip() == 'now'
    assert 'm' in format_age(time.time() - 300)
    assert 'h' in format_age(time.time() - 7200)
    assert 'd' in format_age(time.time() - 200000)


def test_name_roundtrip(tmp_path):
    save_name(str(tmp_path), 'abc', 'Custom Name')
    assert load_name(str(tmp_path), 'abc') == 'Custom Name'
    save_name(str(tmp_path), 'abc', '')
    assert load_name(str(tmp_path), 'abc') == ''


def test_extra_paths_roundtrip(tmp_path):
    save_extra_paths(str(tmp_path), [r'C:\tools', r'D:\bin'])
    assert load_extra_paths(str(tmp_path)) == [r'C:\tools', r'D:\bin']
