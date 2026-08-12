r"""A value going into an inline handler crosses two parsers, not one.

The markup writes `onchange="ccSet('k',this,'${esc(a.dir)}')"`. The browser
unescapes the ATTRIBUTE first, and then JS parses what is left as a string
literal — so a Windows path's backslashes are read as escape sequences:
`C:\Users\mab\.claude` becomes `C:Usersmab.claude`. The settings editor posted
that mangled value as `cfgdir`, the account allowlist correctly refused it, and
every save came back "invalid cfgdir".

Two call sites had each open-coded the same `.replace(/\\/g,'\\\\')` before
this, which is exactly the shape of thing the third caller forgets.
"""
import re

from claude_sessions.gui_html import PAGE

_JS = PAGE[PAGE.index('<script>'):]

#: a value with one of these words in its expression is a filesystem path
_PATHY = re.compile(r'\b(dir|path|file|cfgdir)\b')


def _interpolated_string_args():
    """Every `'${expr}'` that sits inside an on*="..." attribute."""
    for m in re.finditer(r'on\w+="[^"]*?\'\$\{([^}]*)\}\'', _JS):
        yield m.group(1)


def test_no_filesystem_path_reaches_an_inline_handler_unescaped():
    bad = [e[:70] for e in _interpolated_string_args()
           if _PATHY.search(e) and 'jsq(' not in e]
    assert not bad, 'paths interpolated into a handler without jsq(): %s' % bad


def test_the_helper_doubles_backslashes_as_well_as_escaping_html():
    line = _JS[_JS.index('function jsq('):]
    line = line[:line.index('\n')]
    assert r"replace(/\\/g,'\\\\')" in line, 'jsq does not double backslashes'
    assert 'esc(' in line, 'jsq must HTML-escape too, not only fix backslashes'


def test_nobody_open_codes_the_backslash_escape_any_more():
    """One helper, or it is a convention again."""
    assert _JS.count(r"replace(/\\/g,'\\\\')") == 1, \
        'the backslash escape is open-coded outside jsq()'


def test_the_settings_editor_passes_an_account_index_not_a_path():
    """Better than escaping: the value never enters the markup at all."""
    assert 'onchange="ccSet(' in _JS
    m = re.search(r'onchange="ccSet\([^"]*\)"', _JS)
    assert m and not _PATHY.search(m.group(0)), m.group(0) if m else 'missing'
    assert 'const a=CCACCTS[ai];' in _JS, 'ccSet no longer resolves by index'
