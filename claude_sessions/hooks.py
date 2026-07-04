"""Hooks manager — template, toggle, and remove Claude Code hooks in
settings.json (user scope ~/.claude/settings.json).

Hooks fire shell commands / prompts on tool events (PreToolUse, PostToolUse,
Stop, ...). This edits the `hooks` block; disabled hooks are parked under
`hooks_disabled` so they round-trip without losing config.
"""

import json
import os

from .config import W, config_dir
from .ui import menu, text_input, flash, pause, confirm, _cls
from . import config as _c
from . import render

settings_path = os.path.join(config_dir, 'settings.json')

# Valid Claude Code hook events (for AI-generation validation).
EVENTS = {'PreToolUse', 'PostToolUse', 'UserPromptSubmit', 'Stop', 'SubagentStop',
          'SessionStart', 'SessionEnd', 'Notification', 'PreCompact'}

# A PreToolUse hook that exits with code 2 BLOCKS the tool and shows its stderr
# to Claude. PowerShell one-liners parse the hook JSON on stdin (tool_input).
_PS = 'powershell -NoProfile -Command'


def _block_bash(pattern, msg):
    return (f"{_PS} \"$j=$input|Out-String|ConvertFrom-Json; "
            f"if($j.tool_input.command -match '{pattern}'){{"
            f"[Console]::Error.WriteLine('claudectl: {msg}'); exit 2}}\"")


def _block_path(field, pattern, msg):
    return (f"{_PS} \"$j=$input|Out-String|ConvertFrom-Json; "
            f"if($j.tool_input.{field} -match '{pattern}'){{"
            f"[Console]::Error.WriteLine('claudectl: {msg}'); exit 2}}\"")


# Ready-made hooks the user can drop in. Windows-friendly (PowerShell for
# JSON parsing / beeps; plain executables for formatters/git).
TEMPLATES = {
    # ── formatting / quality ──────────────────────────────────
    'prettier-on-edit': {
        'event': 'PostToolUse',
        'entry': {'matcher': 'Edit|Write|MultiEdit',
                  'hooks': [{'type': 'command', 'command': 'prettier --write .'}]},
        'desc': 'Prettier-format the project after every edit',
    },
    'ruff-format-python': {
        'event': 'PostToolUse',
        'entry': {'matcher': 'Edit|Write|MultiEdit',
                  'hooks': [{'type': 'command', 'command': 'ruff format . && ruff check --fix .'}]},
        'desc': 'Ruff format + autofix Python after edits',
    },
    'eslint-fix-on-edit': {
        'event': 'PostToolUse',
        'entry': {'matcher': 'Edit|Write|MultiEdit',
                  'hooks': [{'type': 'command', 'command': 'eslint --fix .'}]},
        'desc': 'ESLint --fix after every edit',
    },
    'gofmt-on-edit': {
        'event': 'PostToolUse',
        'entry': {'matcher': 'Edit|Write|MultiEdit',
                  'hooks': [{'type': 'command', 'command': 'gofmt -w .'}]},
        'desc': 'gofmt the project after edits',
    },
    'run-tests-on-stop': {
        'event': 'Stop',
        'entry': {'hooks': [{'type': 'command', 'command': 'pytest -q'}]},
        'desc': 'Run pytest when Claude finishes a turn',
    },
    # ── safety / guardrails (exit 2 blocks the tool) ──────────
    'block-rm-rf': {
        'event': 'PreToolUse',
        'entry': {'matcher': 'Bash',
                  'hooks': [{'type': 'command',
                             'command': _block_bash('rm\\s+-rf', 'rm -rf blocked')}]},
        'desc': 'Block rm -rf commands',
    },
    'block-git-reset-hard': {
        'event': 'PreToolUse',
        'entry': {'matcher': 'Bash',
                  'hooks': [{'type': 'command',
                             'command': _block_bash('git\\s+reset\\s+--hard', 'git reset --hard blocked')}]},
        'desc': 'Block git reset --hard',
    },
    'block-force-push': {
        'event': 'PreToolUse',
        'entry': {'matcher': 'Bash',
                  'hooks': [{'type': 'command',
                             'command': _block_bash('push.*--force', 'force push blocked')}]},
        'desc': 'Block git push --force',
    },
    'block-sudo': {
        'event': 'PreToolUse',
        'entry': {'matcher': 'Bash(sudo:*)',
                  'hooks': [{'type': 'command', 'command': 'echo "sudo blocked" 1>&2 && exit 2'}]},
        'desc': 'Block sudo commands',
    },
    'block-curl': {
        'event': 'PreToolUse',
        'entry': {'matcher': 'Bash(curl:*)',
                  'hooks': [{'type': 'command', 'command': 'echo "curl blocked" 1>&2 && exit 2'}]},
        'desc': 'Block bash curl commands',
    },
    'protect-env-read': {
        'event': 'PreToolUse',
        'entry': {'matcher': 'Read',
                  'hooks': [{'type': 'command',
                             'command': _block_path('file_path', '\\.env', 'refusing to read .env')}]},
        'desc': 'Block reading .env files (secrets)',
    },
    'protect-secret-write': {
        'event': 'PreToolUse',
        'entry': {'matcher': 'Write|Edit|MultiEdit',
                  'hooks': [{'type': 'command',
                             'command': _block_path('file_path', '\\.env|credentials|id_rsa|\\.pem',
                                                    'refusing to write to a secret file')}]},
        'desc': 'Block writing to .env / credential files',
    },
    # ── audit / notifications / context ───────────────────────
    'log-bash-commands': {
        'event': 'PostToolUse',
        'entry': {'matcher': 'Bash',
                  'hooks': [{'type': 'command',
                             'command': (f"{_PS} \"$j=$input|Out-String|ConvertFrom-Json; "
                                         "Add-Content -Path .claudectl\\bash-log.txt "
                                         "-Value $j.tool_input.command\"")}]},
        'desc': 'Append every Bash command to .claudectl/bash-log.txt',
    },
    'notify-on-stop': {
        'event': 'Stop',
        'entry': {'hooks': [{'type': 'command',
                             'command': 'powershell -c "[console]::beep(800,200)"'}]},
        'desc': 'Beep when Claude finishes a turn',
    },
    'notify-on-input-needed': {
        'event': 'Notification',
        'entry': {'hooks': [{'type': 'command',
                             'command': 'powershell -c "[console]::beep(1000,150);[console]::beep(1000,150)"'}]},
        'desc': 'Double-beep when Claude needs your input',
    },
    'session-start-git-status': {
        'event': 'SessionStart',
        'entry': {'hooks': [{'type': 'command', 'command': 'git status -sb'}]},
        'desc': 'Inject git branch + status at session start',
    },
}


def _memory_hook_command():
    import sys
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'recall_hook.py')
    return f'"{sys.executable}" "{script}"'


def install_memory_hook():
    """Idempotently install (or repair) the UserPromptSubmit recall hook in
    user-scope settings.json. Returns True when present after the call."""
    s = _load()
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
                    return _save(s)
                return True
    entries.append({'hooks': [{'type': 'command', 'command': cmd, 'timeout': 5}]})
    return _save(s)


def uninstall_memory_hook():
    """Remove the recall hook from user-scope settings.json."""
    s = _load()
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
    return _save(s) if changed else True


def memory_hook_installed():
    entries = (_load().get('hooks') or {}).get('UserPromptSubmit') or []
    return any('recall_hook.py' in str(h.get('command', ''))
               for e in entries if isinstance(e, dict)
               for h in (e.get('hooks') or []))


def _load():
    try:
        with open(settings_path, encoding='utf-8') as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save(d):
    try:
        os.makedirs(os.path.dirname(settings_path), exist_ok=True)
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(d, f, indent=2)
        return True
    except Exception:
        return False


def _count(block):
    return sum(len(v) if isinstance(v, list) else 0 for v in (block or {}).values())


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
                items.append((f"{_c.C_OK}●{_c.C_RESET} {event}  {_c.C_DIM}{m}{_c.C_RESET}",
                              f'on:{event}:{i}'))
        for event, entries in disabled.items():
            for i, e in enumerate(entries if isinstance(entries, list) else []):
                m = e.get('matcher', '(any)')
                items.append((f"{_c.C_DIM}○ {event}  {m} (disabled){_c.C_RESET}",
                              f'off:{event}:{i}'))
        if not items:
            items.append((f"{_c.C_DIM}(no hooks configured){_c.C_RESET}", None))
        items += [(f"{'─' * W}", None),
                  ('＋  Add from template', '__tpl__'),
                  ('✨  AI-generate a hook (Claude)', '__ai__'),
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
    data = memory._parse_json(memory._claude_stdin(
        prompt, os.getcwd(), crumbs=('CLAUDECTL', 'HOOK'),
        label='Generating hook with Claude...'))
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
