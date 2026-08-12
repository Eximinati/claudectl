"""A typed editor for Claude Code's own settings.json, per account.

claudectl wrote four of roughly eighty documented keys, all of them indirectly
(hooks, permissions, outputStyle, statusLine), and offered no way to see or set
the rest — so the file had to be edited by hand in a text editor, which is
exactly the workflow claudectl exists to remove.

Two constraints shape this module:

- **Read-modify-write, never rewrite.** The same file carries hooks,
  permissions, plugin state and whatever a future version adds. Only the key
  being edited is touched, through `hooks._load`/`_save`, so there is still one
  reader and one writer for that file.
- **Per account.** `cfgdir` reaches every function, on Phase 0's accessors.
  A setting is a property of the account it is written into.

The schema is what makes the editor typed: a key's kind decides the control the
UI draws and the validation applied before anything is written.
"""

from . import hooks

__all__ = ['SCHEMA', 'read', 'write', 'read_all']

#: (kind, choices, help, group). kind: bool | str | int | enum | list | json
#:
#: Only keys claudectl can validate are here. A key it does not know is still
#: preserved — nothing outside this table is ever touched.
#:
#: `group` exists for the editor: twenty-one raw camelCase keys in one flat
#: list is a wall, and the answer to "where do I change how much it thinks" is
#: not findable by scanning it. The order of this dict IS the display order.
SCHEMA = {
    # — how it answers —
    'model':                  ('str', [], 'Default model id for new sessions',
                               'Model & reasoning'),
    'fallbackModel':          ('str', [], 'Model used when the primary is overloaded',
                               'Model & reasoning'),
    'availableModels':        ('list', [], 'Restrict the model picker to these ids',
                               'Model & reasoning'),
    'effortLevel':            ('enum', ['low', 'medium', 'high', 'xhigh', 'max'],
                               'Default reasoning effort', 'Model & reasoning'),
    'alwaysThinkingEnabled':  ('bool', [], 'Think before every response',
                               'Model & reasoning'),
    # — what it remembers —
    'autoCompactEnabled':     ('bool', [], 'Compact the context automatically',
                               'Context & memory'),
    'autoCompactWindow':      ('int', [], 'Tokens of context to keep when compacting',
                               'Context & memory'),
    'autoMemoryEnabled':      ('bool', [], "Let Claude Code maintain its own memory",
                               'Context & memory'),
    'claudeMdExcludes':       ('list', [], 'Glob patterns of CLAUDE.md files to skip',
                               'Context & memory'),
    # — the terminal —
    # fullscreen vs classic is not cosmetic: an installed statusLine is simply
    # not drawn by the classic renderer, silently — see statusline.blockers
    'tui':                    ('enum', ['fullscreen', 'default'],
                               'Renderer. The statusline only shows in fullscreen',
                               'Editing & interface'),
    'editorMode':             ('enum', ['normal', 'vim'], 'Prompt editing mode',
                               'Editing & interface'),
    'theme':                  ('str', [], "Claude Code's own colour theme",
                               'Editing & interface'),
    'axScreenReader':         ('bool', [], 'Screen-reader friendly output',
                               'Editing & interface'),
    # — what it keeps and how it updates —
    'cleanupPeriodDays':      ('int', [], 'Days of transcripts and snapshots to keep',
                               'Sessions & maintenance'),
    'fileCheckpointingEnabled': ('bool', [], 'Snapshot files before edits (/rewind)',
                                 'Sessions & maintenance'),
    'autoUpdatesChannel':     ('enum', ['stable', 'latest'], 'Which build to update to',
                               'Sessions & maintenance'),
    # — what it is allowed to load —
    'teammateMode':           ('str', [], 'Agent-teams behaviour', 'Teams & extensions'),
    'disableAllHooks':        ('bool', [], 'Master switch for every hook',
                               'Teams & extensions'),
    'disableBundledSkills':   ('bool', [], 'Do not load the built-in skills',
                               'Teams & extensions'),
    # — raw JSON, for the ones with no simpler shape —
    'attribution':            ('json', [], 'Co-authored-by / commit attribution',
                               'Advanced'),
    'env':                    ('json', [], 'Environment variables for every session',
                               'Advanced'),
    'sandbox':                ('json', [], 'Sandboxing policy (macOS/Linux/WSL2 only)',
                               'Advanced'),
}

#: display order, taken from SCHEMA rather than repeated
GROUPS = list(dict.fromkeys(v[3] for v in SCHEMA.values()))


def read(cfgdir=None):
    """{key: value} for every schema key the account actually sets."""
    s = hooks._load(cfgdir)
    return {k: s[k] for k in SCHEMA if k in s}


def read_all():
    """Per account, so the UI can show that two accounts disagree — which is
    the state a machine is in after anything was configured by hand."""
    return {name: read(d) for name, d in hooks.account_dirs()}


def write(key, value, cfgdir=None):
    """Set or clear ONE key. Returns (ok, message).

    Clearing is REMOVING the key, never writing a falsy value: `False` and
    `absent` mean different things to Claude Code, and pinning a literal
    freezes behaviour against a future change in what the default means — the
    lesson `outputStyle: 'default'` already taught this codebase.
    """
    if key not in SCHEMA:
        return False, 'unknown setting %r' % (key,)
    kind, choices = SCHEMA[key][0], SCHEMA[key][1]
    if value is None or value == '':
        s = hooks._load(cfgdir)
        if key not in s:
            return True, 'already unset'
        s.pop(key)
        return bool(hooks._save(s, cfgdir)), 'cleared %s' % key
    ok, coerced = _coerce(kind, choices, value)
    if not ok:
        return False, coerced
    s = hooks._load(cfgdir)
    s[key] = coerced
    return bool(hooks._save(s, cfgdir)), 'set %s' % key


def _coerce(kind, choices, value):
    """(ok, value_or_error). The validation is the point of the schema: this
    file is parsed by Claude Code, and a wrongly-typed value is a startup
    error the user sees instead of their session."""
    if kind == 'bool':
        if isinstance(value, bool):
            return True, value
        if str(value).lower() in ('true', '1', 'yes', 'on'):
            return True, True
        if str(value).lower() in ('false', '0', 'no', 'off'):
            return True, False
        return False, 'expected true or false'
    if kind == 'int':
        try:
            return True, int(value)
        except (TypeError, ValueError):
            return False, 'expected a whole number'
    if kind == 'enum':
        if value in choices:
            return True, value
        return False, 'expected one of: %s' % ', '.join(choices)
    if kind == 'list':
        if isinstance(value, list):
            items = value
        else:
            items = [v.strip() for v in str(value).replace(',', '\n').split('\n')]
        items = [v for v in items if v]
        return True, items
    if kind == 'json':
        if isinstance(value, (dict, list)):
            return True, value
        import json
        try:
            parsed = json.loads(value)
        except Exception as e:
            return False, 'not valid JSON: %s' % e
        if not isinstance(parsed, (dict, list)):
            return False, 'expected a JSON object or array'
        return True, parsed
    return True, str(value)
