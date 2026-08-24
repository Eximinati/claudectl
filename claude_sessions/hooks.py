"""Hooks manager — template, toggle, and remove Claude Code hooks in
settings.json (user scope ~/.claude/settings.json).

Hooks fire shell commands / prompts on tool events (PreToolUse, PostToolUse,
Stop, ...). This edits the `hooks` block; disabled hooks are parked under
`hooks_disabled` so they round-trip without losing config.
"""

import json
import os
import re
import sys

from .config import W, config_dir
from .ui import menu, text_input, flash, pause, confirm, _cls
from . import config as _c
from . import render

settings_path = os.path.join(config_dir, 'settings.json')

# Valid Claude Code hook events.
#: All 31 of them. The manager used to know 18, which meant the other 13 could
#: neither be placed nor even SEEN — a hook someone had configured by hand in
#: one of those events was invisible in a screen that claimed to list them.
#: The value is the matcher's meaning, or '' where the event takes none; the
#: manager uses it to prompt for the right thing instead of a generic string.
EVENT_MATCHERS = {
    'PreToolUse': 'tool name',
    'PostToolUse': 'tool name',
    'PostToolUseFailure': 'tool name',
    'PostToolBatch': '',
    'UserPromptSubmit': '',
    'UserPromptExpansion': 'command name',
    'Stop': '',
    'StopFailure': 'error type',
    'SubagentStart': 'agent type',
    'SubagentStop': 'agent type',
    'SessionStart': 'startup | resume | clear | compact | fork',
    'SessionEnd': 'end reason',
    'Setup': 'init | maintenance',
    'Notification': 'notification type',
    'MessageDisplay': '',
    'PreCompact': 'manual | auto',
    'PostCompact': 'manual | auto',
    'InstructionsLoaded': 'load reason',
    'PermissionRequest': 'tool name',
    'PermissionDenied': 'tool name',
    'ConfigChange': 'configuration source',
    'CwdChanged': '',
    'DirectoryAdded': '',
    'WorktreeCreate': '',
    'WorktreeRemove': '',
    'TaskCreated': '',
    'TaskCompleted': '',
    'TeammateIdle': '',
    'FileChanged': 'filenames to watch',
    'Elicitation': 'MCP server name',
    'ElicitationResult': 'MCP server name',
}

EVENTS = set(EVENT_MATCHERS)

def _py_hook(script):
    """Absolute `"<python>" "<claude_sessions/script>"` — runs regardless of the
    hook shell (bash/cmd/pwsh) and doesn't depend on $-expansion."""
    import sys
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), script)
    return f'"{sys.executable}" "{p}"'


def _beep(times):
    """An audible ping, per platform. PowerShell's [console]::beep exists only
    on Windows; macOS has afplay/osascript, and a POSIX terminal takes a bare
    BEL, which `printf` emits without needing a subshell that supports \\a."""
    if os.name == 'nt':
        one = '[console]::beep(%d,%d)' % (800 if times == 1 else 1000,
                                          200 if times == 1 else 150)
        return 'powershell -c "%s"' % ';'.join([one] * times)
    if sys.platform == 'darwin':
        return ';'.join(['osascript -e "beep"'] * times)
    return "printf '%s'" % (r'\a' * times)


def _guard(field, pattern, msg):
    """A PreToolUse guard: block (exit 2) when tool_input[field] matches pattern.
    Runs guard_hook.py via Python (shell-agnostic; no PowerShell/bash quirks)."""
    return f'{_py_hook("guard_hook.py")} {field} "{pattern}" "{msg}"'


def _fmt(bin_name, cmd):
    """Formatter guarded so a MISSING binary is a silent no-op, not an error
    (POSIX shell — the hook shell on this setup). Edit for cmd-only shells."""
    return f'command -v {bin_name} >/dev/null 2>&1 && {cmd} || true'


# Ready-made hooks the user can drop in. Blocks use a bundled Python guard
# (shell-agnostic); formatters are guarded so a missing tool won't error.
TEMPLATES = {
    # ── formatting / quality ──────────────────────────────────
    'prettier-on-edit': {
        'event': 'PostToolUse',
        'entry': {'matcher': 'Edit|Write|MultiEdit',
                  'hooks': [{'type': 'command', 'command': _fmt('prettier', 'prettier --write .')}]},
        'desc': 'Prettier-format the project after every edit',
    },
    'ruff-format-python': {
        'event': 'PostToolUse',
        'entry': {'matcher': 'Edit|Write|MultiEdit',
                  'hooks': [{'type': 'command',
                             'command': _fmt('ruff', 'ruff format . && ruff check --fix .')}]},
        'desc': 'Ruff format + autofix Python after edits',
    },
    'eslint-fix-on-edit': {
        'event': 'PostToolUse',
        'entry': {'matcher': 'Edit|Write|MultiEdit',
                  'hooks': [{'type': 'command', 'command': _fmt('eslint', 'eslint --fix .')}]},
        'desc': 'ESLint --fix after every edit',
    },
    'gofmt-on-edit': {
        'event': 'PostToolUse',
        'entry': {'matcher': 'Edit|Write|MultiEdit',
                  'hooks': [{'type': 'command', 'command': _fmt('gofmt', 'gofmt -w .')}]},
        'desc': 'gofmt the project after edits',
    },
    'run-tests-on-stop': {
        'event': 'Stop',
        'entry': {'hooks': [{'type': 'command', 'command': _fmt('pytest', 'pytest -q')}]},
        'desc': 'Run pytest when Claude finishes a turn',
    },
    # ── safety / guardrails (exit 2 blocks the tool) ──────────
    'block-rm-rf': {
        'event': 'PreToolUse',
        'entry': {'matcher': 'Bash',
                  'hooks': [{'type': 'command', 'command': _guard('command', 'rm\\s+-rf', 'rm -rf blocked')}]},
        'desc': 'Block rm -rf commands',
    },
    'block-git-reset-hard': {
        'event': 'PreToolUse',
        'entry': {'matcher': 'Bash',
                  'hooks': [{'type': 'command',
                             'command': _guard('command', 'git\\s+reset\\s+--hard', 'git reset --hard blocked')}]},
        'desc': 'Block git reset --hard',
    },
    'block-force-push': {
        'event': 'PreToolUse',
        'entry': {'matcher': 'Bash',
                  'hooks': [{'type': 'command',
                             'command': _guard('command', 'push.*--force', 'force push blocked')}]},
        'desc': 'Block git push --force',
    },
    'block-sudo': {
        'event': 'PreToolUse',
        'entry': {'matcher': 'Bash',
                  'hooks': [{'type': 'command', 'command': _guard('command', '\\bsudo\\b', 'sudo blocked')}]},
        'desc': 'Block sudo commands',
    },
    'block-curl': {
        'event': 'PreToolUse',
        'entry': {'matcher': 'Bash',
                  'hooks': [{'type': 'command', 'command': _guard('command', '\\bcurl\\b', 'curl blocked')}]},
        'desc': 'Block bash curl commands',
    },
    'protect-env-read': {
        'event': 'PreToolUse',
        'entry': {'matcher': 'Read',
                  'hooks': [{'type': 'command', 'command': _guard('file_path', '\\.env', 'refusing to read .env')}]},
        'desc': 'Block reading .env files (secrets)',
    },
    'protect-secret-write': {
        'event': 'PreToolUse',
        'entry': {'matcher': 'Write|Edit|MultiEdit',
                  'hooks': [{'type': 'command',
                             'command': _guard('file_path', '\\.env|credentials|id_rsa|\\.pem',
                                               'refusing to write to a secret file')}]},
        'desc': 'Block writing to .env / credential files',
    },
    # ── audit / notifications / context ───────────────────────
    'log-bash-commands': {
        'event': 'PostToolUse',
        'entry': {'matcher': 'Bash',
                  'hooks': [{'type': 'command', 'command': _py_hook('logbash_hook.py')}]},
        'desc': 'Append every Bash command to .claudectl/bash-log.txt',
    },
    'notify-on-stop': {
        'event': 'Stop',
        'entry': {'hooks': [{'type': 'command', 'command': _beep(1)}]},
        'desc': 'Beep when Claude finishes a turn',
    },
    'notify-on-input-needed': {
        'event': 'Notification',
        'entry': {'hooks': [{'type': 'command', 'command': _beep(2)}]},
        'desc': 'Double-beep when Claude needs your input',
    },
    'session-start-git-status': {
        'event': 'SessionStart',
        'entry': {'hooks': [{'type': 'command', 'command': 'git status -sb'}]},
        'desc': 'Inject git branch + status at session start',
    },
    'minimal-code': {
        'event': 'SessionStart',
        'entry': {'hooks': [{'type': 'command', 'command': _py_hook('minimalcode_hook.py')}]},
        'desc': 'Inject a compact code-minimization rule each session (anti over-engineering)',
    },
    # ── token savers ──────────────────────────────────────────
    'concise-output': {
        'event': 'SessionStart',
        'entry': {'hooks': [{'type': 'command', 'command': _py_hook('concise_hook.py')}]},
        'desc': 'Cut output tokens: no narration, no re-printed code (saves tokens)',
    },
    'filter-test-output': {
        'event': 'PreToolUse',
        'entry': {'matcher': 'Bash',
                  'hooks': [{'type': 'command', 'command': _py_hook('testfilter_hook.py')}]},
        'desc': 'Pipe pytest/npm test/go test output through a failures-only filter (saves tokens)',
    },
    # ── lifecycle events claudectl has a specific reason to want ──────
    # Two of these replace approximations with the real signal.
    'reinject-after-compact': {
        # THE one worth having. claudectl already advertises "context-loss
        # insurance after /compact", but until PostCompact existed the only
        # available moment was SessionStart — i.e. before the loss, not after
        # it. This fires on the far side of a compaction, when the context has
        # actually been thrown away and re-injecting memory is the whole point.
        'event': 'PostCompact',
        'entry': {'hooks': [{'type': 'command', 'command': _py_hook('recall_hook.py')}]},
        'desc': 'Re-inject project memory right after /compact discards the context',
    },
    'memory-stale-on-change': {
        # The scheduler polls every auto_memory_interval seconds and hashes to
        # decide whether anything changed. FileChanged says so directly, so the
        # poll stops being the mechanism and becomes the fallback.
        'event': 'FileChanged',
        'entry': {'hooks': [{'type': 'command',
                             'command': _py_hook('worklog_hook.py')}]},
        'desc': 'Mark project memory stale the moment a file changes (instead of polling)',
    },
    'log-permission-denials': {
        # feeds the permission-fatigue work: what actually gets denied, rather
        # than what someone guessed would be. --denied writes the STRUCTURED
        # sidecar (.claudectl/denied.jsonl); without the flag this same script
        # is the plain bash log, where a denial was indistinguishable from a
        # success and every non-Bash denial was dropped on the floor.
        'event': 'PermissionDenied',
        'entry': {'hooks': [{'type': 'command',
                             'command': _py_hook('logbash_hook.py') + ' --denied'}]},
        'desc': 'Record every denied permission (tool, target, reason) so the '
                'allowlist and auto-mode proposals learn from real ones',
    },
    'notify-on-subagent-finish': {
        'event': 'SubagentStop',
        'entry': {'hooks': [{'type': 'command',
                             'command': 'echo "subagent finished"'}]},
        'desc': 'Print a line when a subagent finishes (swap the command for your notifier)',
    },
    'learn-on-session-end': {
        # the natural trigger for the auto-memory cycle: a session that just
        # ended is a session worth mining
        'event': 'SessionEnd',
        'entry': {'hooks': [{'type': 'command', 'command': _py_hook('worklog_hook.py')}]},
        'desc': 'Record the session on exit so auto-memory has it to learn from',
    },
    'log-failed-tools': {
        # a turn that failed is the one worth reading back later, and it is
        # exactly what PostToolUse cannot see
        'event': 'PostToolUseFailure',
        'entry': {'hooks': [{'type': 'command', 'command': _py_hook('logbash_hook.py')}]},
        'desc': 'Record every tool failure alongside the bash log',
    },
    'log-failed-turns': {
        'event': 'StopFailure',
        'entry': {'hooks': [{'type': 'command', 'command': _py_hook('logbash_hook.py')}]},
        'desc': 'Record turns that ended in failure rather than completion',
    },
    'audit-loaded-context': {
        # pairs with the Context Weight Audit: that screen ESTIMATES what will
        # load, this says what actually did
        'event': 'InstructionsLoaded',
        'entry': {'hooks': [{'type': 'command', 'command': _py_hook('logbash_hook.py')}]},
        'desc': 'Record what context actually loaded (pairs with the context audit)',
    },
    'notify-config-change': {
        'event': 'ConfigChange',
        'entry': {'hooks': [{'type': 'command', 'command': _beep(1)}]},
        'desc': 'Beep when something changes settings.json under you',
    },
    'memory-stale-on-cwd-change': {
        'event': 'CwdChanged',
        'entry': {'hooks': [{'type': 'command', 'command': _py_hook('worklog_hook.py')}]},
        'desc': 'Re-evaluate project memory when the session changes directory',
    },
    'notify-teammate-idle': {
        'event': 'TeammateIdle',
        'entry': {'hooks': [{'type': 'command', 'command': _beep(2)}]},
        'desc': 'Double-beep when an agent teammate goes idle and needs work',
    },
}


def _memory_hook_command():
    import sys
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'recall_hook.py')
    return f'"{sys.executable}" "{script}"'


def install_memory_hook(cfgdir=None):
    """Idempotently install (or repair) the UserPromptSubmit recall hook in
    user-scope settings.json. Returns True when present after the call."""
    s = _load(cfgdir)
    hooks = s.setdefault('hooks', {})
    entries = hooks.setdefault('UserPromptSubmit', [])
    if not isinstance(entries, list):
        return False
    cmd = _memory_hook_command()
    for entry in entries:
        for h in (entry.get('hooks') or []):
            if 'recall_hook.py' in str(h.get('command', '')):
                if h.get('command') != cmd:      # stale python/repo path → repair
                    h['command'] = cmd
                    h['timeout'] = 5
                    return _save(s, cfgdir)
                return True
    entries.append({'hooks': [{'type': 'command', 'command': cmd, 'timeout': 5}]})
    return _save(s, cfgdir)


def uninstall_memory_hook(cfgdir=None):
    """Remove the recall hook from user-scope settings.json."""
    s = _load(cfgdir)
    entries = (s.get('hooks') or {}).get('UserPromptSubmit')
    if not isinstance(entries, list):
        return True
    changed = False
    for entry in list(entries):
        hs = entry.get('hooks') or []
        kept = [h for h in hs if 'recall_hook.py' not in str(h.get('command', ''))]
        if len(kept) != len(hs):
            changed = True
            if kept:
                entry['hooks'] = kept
            else:
                entries.remove(entry)
    if changed and not entries:
        s['hooks'].pop('UserPromptSubmit', None)
    return _save(s, cfgdir) if changed else True


def memory_hook_installed(cfgdir=None):
    entries = (_load(cfgdir).get('hooks') or {}).get('UserPromptSubmit') or []
    return any('recall_hook.py' in str(h.get('command', ''))
               for e in entries if isinstance(e, dict)
               for h in (e.get('hooks') or []))


# ── recent-work (worklog) hook: SessionStart inject + Stop capture ──

def _worklog_hook_command():
    import sys
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'worklog_hook.py')
    return f'"{sys.executable}" "{script}"'


# one script serves both events; per-project opt-in is checked inside the script.
# SessionEnd, NOT Stop: Stop fires on EVERY turn and the capture re-streams the
# whole growing transcript each time. The capture is heuristic and only needs to
# run once, when the session is actually over.
_WORKLOG_EVENTS = ('SessionStart', 'SessionEnd')


def install_worklog_hook(cfgdir=None):
    """Idempotently install (or repair) the recent-work hook on SessionStart +
    Stop in user-scope settings.json. Returns True when present after."""
    s = _load(cfgdir)
    hooks = s.setdefault('hooks', {})
    cmd = _worklog_hook_command()
    changed = False
    for event in _WORKLOG_EVENTS:
        entries = hooks.setdefault(event, [])
        if not isinstance(entries, list):
            continue
        found = False
        for entry in entries:
            for h in (entry.get('hooks') or []):
                if 'worklog_hook.py' in str(h.get('command', '')):
                    found = True
                    if h.get('command') != cmd:
                        h['command'] = cmd
                        h['timeout'] = 10
                        changed = True
        if not found:
            entries.append({'hooks': [{'type': 'command', 'command': cmd, 'timeout': 10}]})
            changed = True
    return _save(s, cfgdir) if changed else True


def uninstall_worklog_hook(cfgdir=None):
    s = _load(cfgdir)
    changed = False
    for event in _WORKLOG_EVENTS:
        entries = (s.get('hooks') or {}).get(event)
        if not isinstance(entries, list):
            continue
        for entry in list(entries):
            hs = entry.get('hooks') or []
            kept = [h for h in hs if 'worklog_hook.py' not in str(h.get('command', ''))]
            if len(kept) != len(hs):
                changed = True
                if kept:
                    entry['hooks'] = kept
                else:
                    entries.remove(entry)
        if not entries:
            s.get('hooks', {}).pop(event, None)
    return _save(s, cfgdir) if changed else True


def worklog_hook_installed(cfgdir=None):
    hooks = _load(cfgdir).get('hooks') or {}
    for event in _WORKLOG_EVENTS:
        for e in hooks.get(event) or []:
            if isinstance(e, dict) and any('worklog_hook.py' in str(h.get('command', ''))
                                           for h in (e.get('hooks') or [])):
                return True
    return False


def settings_path_for(cfgdir=None):
    """The settings.json of ONE account — the active one when cfgdir is None.

    `settings_path` deliberately stays the cfgdir=None answer instead of being
    recomputed from `_c.config_dir` here. It is bound at import, which is the
    bug this parameter exists to fix, but it is also the attribute nine tests
    monkeypatch to redirect writes into a tmp dir. Keeping it as the default
    means every one of those still works and the diff stays confined to the
    accessors, rather than becoming a nine-file test rewrite for no behaviour.
    """
    return os.path.join(cfgdir, 'settings.json') if cfgdir else settings_path


def account_dirs():
    """[(name, dir)] for every account, default first. The fan-out target for
    anything that installs into settings.json: a hook or a statusline the user
    asked for is a property of THEM, not of whichever account happened to be
    active when the module was imported."""
    return _c.all_config_dirs()


def across_accounts(fn, *args, **kw):
    """Run an account-scoped accessor against EVERY account -> {name: result}.

    Every `install_*`/`uninstall_*`/`*_installed` below takes `cfgdir`, so one
    helper covers all of them and there is no per-feature `_all` variant to
    forget to add. Returning a dict per account rather than a single bool is
    deliberate: the interesting state is PARTIAL installation, which is what a
    machine looks like after the pre-fix single-account behaviour, and a
    collapsed bool cannot express it.
    """
    return {name: fn(*args, cfgdir=d, **kw) for name, d in account_dirs()}


def _load(cfgdir=None):
    """Claude Code's own settings.json. A corrupt one is MOVED ASIDE, not
    treated as empty: every writer here read-modify-writes, so returning {}
    for a file that exists but will not parse erases the user's hooks,
    permissions and outputStyle on the next save."""
    from . import jsonstore
    return jsonstore.load(settings_path_for(cfgdir), expect=dict)


def _save(d, cfgdir=None):
    return _c.write_json_atomic(settings_path_for(cfgdir), d)


def _count(block):
    return sum(len(v) if isinstance(v, list) else 0 for v in (block or {}).values())


def _entry_commands(entry):
    """All hook command strings inside one settings entry."""
    return [str(h.get('command', ''))
            for h in (entry.get('hooks') or []) if isinstance(h, dict)]


# bundled hook scripts → friendly name (matcher/event alone can't tell them apart)
_SCRIPT_LABELS = {
    'recall_hook.py': 'recall (project memory)',
    'worklog_hook.py': 'recent-work memory',
    'minimalcode_hook.py': 'minimal-code',
    'concise_hook.py': 'concise-output',
    'testfilter_hook.py': 'filter-test-output',
    'guard_hook.py': 'guard/block',
    'logbash_hook.py': 'log-bash-commands',
}


#: `_py_hook` bakes `sys.executable` into the command, and that is
#: `pythonw.exe` when claudectl runs as a GUI but `python.exe` from a console.
#: The same template installed from the two shells therefore produced two
#: strings that were not equal — two entries in settings.json, and a row that
#: never went "installed" because the running process had generated the other
#: spelling. What identifies a hook is the script and its arguments, not which
#: interpreter happens to launch it.
_PYEXE = re.compile(r'^"?[^"]*?python(w)?(\.exe)?"?\s+', re.I)


def _cmd_keys(entry):
    """A hook's commands reduced to their identity, interpreter-independent."""
    return [_PYEXE.sub('', (c or '').strip()) for c in _entry_commands(entry)]


def _hook_label(entry, event=None):
    """Identify what a configured hook actually is: its template name if the
    command matches a known template/bundled script, else a short command
    snippet — so several hooks on the same event/matcher are distinguishable.

    ORDER MATTERS, and it used to be wrong. The per-script table was consulted
    first, so every template built on a shared bundled script answered with the
    script's name instead of its own key: all seven block-*/protect-* hooks came
    back as 'guard/block', reinject-after-compact as 'recall (project memory)',
    learn-on-session-end as 'recent-work memory'. The manager decides whether a
    template is installed by looking for its key among these labels, so eleven
    templates could never show as installed no matter how many times you
    installed them. The template match is strictly more specific and now runs
    first; the script table is the fallback for hooks the user wrote by hand.

    `event` disambiguates the case the command alone cannot: two templates that
    run the same script at different moments. Without it a match is only
    accepted when exactly one template owns that command.
    """
    cmds = _cmd_keys(entry)
    if cmds:
        same = [k for k, t in TEMPLATES.items()
                if _cmd_keys(t['entry']) == cmds]
        if event is not None:
            same = [k for k in same if TEMPLATES[k]['event'] == event] or same
        if len(same) == 1:
            return same[0]
    raw = _entry_commands(entry)
    joined = ' '.join(raw)
    for script, name in _SCRIPT_LABELS.items():
        if script in joined:
            return name
    snippet = (raw[0] if raw else '').strip()
    return (snippet[:44] + '…') if len(snippet) > 45 else (snippet or '(empty)')


def hooks_menu(scope=None):
    """List configured hooks; insert templates; toggle/remove."""
    while True:
        s = _load()
        hooks = s.get('hooks', {})
        disabled = s.get('hooks_disabled', {})
        items = []
        for event, entries in hooks.items():
            for i, e in enumerate(entries if isinstance(entries, list) else []):
                m = e.get('matcher', '(any)')
                label = _hook_label(e, event)
                items.append((f"{_c.C_OK}●{_c.C_RESET} {event}  {_c.C_DIM}{m}{_c.C_RESET}"
                              f"  {_c.C_NAME}{label}{_c.C_RESET}",
                              f'on:{event}:{i}'))
        for event, entries in disabled.items():
            for i, e in enumerate(entries if isinstance(entries, list) else []):
                m = e.get('matcher', '(any)')
                label = _hook_label(e, event)
                items.append((f"{_c.C_DIM}○ {event}  {m}  {label} (disabled){_c.C_RESET}",
                              f'off:{event}:{i}'))
        if not items:
            items.append((f"{_c.C_DIM}(no hooks configured){_c.C_RESET}", None))
        items += [(f"{'─' * W}", None),
                  ('＋  Add from template', '__tpl__'),
                  ('✨  AI-generate a hook (Claude)', '__ai__'),
                  ('🧹  Remove broken/legacy hooks', '__purge__'),
                  ('📝  Edit settings.json', '__edit__')]

        sel = menu(items, f"HOOKS  /  {os.path.basename(config_dir)}")
        if not sel:
            return
        if sel == '__edit__':
            from .config import open_in_editor
            if not os.path.exists(settings_path):
                _save(_load())
            open_in_editor(settings_path)
        elif sel == '__tpl__':
            _add_template()
        elif sel == '__ai__':
            _ai_hook()
        elif sel == '__purge__':
            _purge_legacy()
        elif sel.startswith(('on:', 'off:')):
            _toggle_or_remove(sel)


def _add_template():
    pick = menu([(f"{k}  —  {v['desc']}", k) for k, v in TEMPLATES.items()],
                "HOOK TEMPLATES")
    if not pick:
        return
    tpl = TEMPLATES[pick]
    s = _load()
    s.setdefault('hooks', {}).setdefault(tpl['event'], []).append(tpl['entry'])
    if _save(s):
        flash(f"Added {pick}")
    else:
        flash("Write failed", ok=False, secs=1.4)


def _is_broken(cmd):
    """A hook command that errors under a bash hook shell: the old PowerShell
    $-parsing blocks, or an unguarded formatter that fails when the tool is
    absent."""
    c = str(cmd or '')
    if 'ConvertFrom-Json' in c:                      # legacy powershell block/log
        return True
    bins = ('prettier', 'eslint', 'gofmt', 'ruff', 'pytest')
    stripped = c.strip()
    if any(stripped.startswith(b) for b in bins) and 'command -v' not in c:
        return True                                  # unguarded formatter
    return False


def _purge_legacy():
    """Remove hook entries whose commands are known to error (old PowerShell
    blocks / unguarded formatters). Re-add the fixed templates afterwards."""
    s = _load()
    removed = 0
    for key in ('hooks', 'hooks_disabled'):
        block = s.get(key, {})
        for event in list(block):
            kept = []
            for entry in block[event]:
                hs = [h for h in (entry.get('hooks') or []) if not _is_broken(h.get('command'))]
                if not hs:
                    removed += 1
                    continue
                if len(hs) != len(entry.get('hooks') or []):
                    removed += 1
                    entry['hooks'] = hs
                kept.append(entry)
            if kept:
                block[event] = kept
            else:
                block.pop(event, None)
    if not removed:
        flash("No broken hooks found", secs=1.4)
        return
    if not confirm(f"Remove {removed} broken/legacy hook(s)?", danger=True):
        return
    flash(f"Removed {removed} broken hook(s) — re-add from templates" if _save(s)
          else "Write failed", ok=bool(removed), secs=2)


def _ai_hook():
    """Describe a hook in plain language; Claude returns a validated hook spec
    (event + matcher + command) which you preview and confirm before it's saved."""
    desc = text_input("Describe the hook (when it fires + what it does):")
    if not desc:
        return
    from . import memory
    prompt = (
        "You configure Claude Code hooks. Given the REQUEST, output ONLY valid "
        "JSON for one hook, no prose, no code fences:\n"
        '{"event":"PreToolUse|PostToolUse|UserPromptSubmit|Stop|SubagentStop|'
        'SessionStart|SessionEnd|Notification|PreCompact",'
        '"matcher":"tool matcher or empty (e.g. Edit|Write, Bash, Bash(git:*))",'
        '"command":"a single shell command; Windows/PowerShell friendly",'
        '"desc":"short description"}\n'
        "Rules: to BLOCK a tool in PreToolUse, the command must write a reason to "
        "stderr and `exit 2`. Hook input arrives as JSON on stdin (fields "
        "tool_name, tool_input). Keep it a one-liner.\n\n"
        f"REQUEST:\n{desc}"
    )
    # the enum comes from EVENTS rather than being retyped — the prompt above
    # already lists a SUBSET, and the two drifting apart is how a hook for a
    # newer event (DirectoryAdded, Setup) gets rejected as invalid
    schema = {'type': 'object',
              'properties': {'event': {'type': 'string', 'enum': sorted(EVENTS)},
                             'matcher': {'type': 'string'},
                             'command': {'type': 'string'},
                             'desc': {'type': 'string'}},
              'required': ['event', 'command']}
    data = memory._claude_json(
        prompt, os.getcwd(), schema, crumbs=('CLAUDECTL', 'HOOK'),
        label='Generating hook with Claude...')
    if not isinstance(data, dict):
        flash("Claude returned no valid hook", ok=False, secs=1.8)
        return
    event = str(data.get('event', '')).strip()
    command = str(data.get('command', '')).strip()
    if event not in EVENTS or not command:
        flash(f"Invalid hook (event={event or '?'})", ok=False, secs=2)
        return
    matcher = str(data.get('matcher', '')).strip()
    _cls()
    print(f"\n  AI-GENERATED HOOK\n")
    print(f"  Event   : {event}")
    print(f"  Matcher : {matcher or '(any)'}")
    print(f"  Command : {command}")
    print(f"  {data.get('desc', '')}\n")
    if not confirm("Add this hook?"):
        return
    entry = {'hooks': [{'type': 'command', 'command': command}]}
    if matcher:
        entry['matcher'] = matcher
    s = _load()
    s.setdefault('hooks', {}).setdefault(event, []).append(entry)
    ok = _save(s)
    flash("Hook added" if ok else "Write failed", ok=ok, secs=1.4)


def _toggle_or_remove(sel):
    state, event, idx = sel.split(':')
    idx = int(idx)
    act = menu([('Toggle enabled/disabled', 'toggle'),
                ('Remove', 'remove'), ('Cancel', 'cancel')], "HOOK")
    if act not in ('toggle', 'remove'):
        return
    s = _load()
    src_key = 'hooks' if state == 'on' else 'hooks_disabled'
    dst_key = 'hooks_disabled' if state == 'on' else 'hooks'
    src = s.get(src_key, {})
    entries = src.get(event, [])
    if idx >= len(entries):
        return
    entry = entries.pop(idx)
    if not entries:
        src.pop(event, None)
    if act == 'toggle':
        s.setdefault(dst_key, {}).setdefault(event, []).append(entry)
        flash("Toggled")
    else:
        if not confirm("Remove this hook?", danger=True):
            return  # don't persist the pop
        flash("Hook removed")
    _save(s)
