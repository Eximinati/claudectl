import os
import json
import shutil

_USERPROFILE = os.environ.get('USERPROFILE') or os.path.expanduser('~')
_TEMP        = os.environ.get('TEMP') or os.environ.get('TMP') or _USERPROFILE

projects_dir = os.path.join(_USERPROFILE, '.claude', 'projects')
choice_file = os.environ.get('CHOICE_FILE', os.path.join(_TEMP, 'choice_claude.txt'))
last_session_file = os.path.join(projects_dir, 'last-session.json')

global_claude_md = os.path.join(_USERPROFILE, '.claude', 'CLAUDE.md')

# ── user settings (~/.claude/claudectl.json) ─────────────────

settings_file = os.path.join(_USERPROFILE, '.claude', 'claudectl.json')

_DEFAULT_SETTINGS = {
    'editor': '',           # path to preferred text editor ('' = auto-detect)
    'claude_exe': '',       # path to claude.exe ('' = auto-detect)
    'default_effort': '',   # preselected effort in launch options
    'default_model': '',    # preselected model in launch options
    'project_defaults': {}, # encoded_name -> {'effort': ..., 'model': ...}
}


def load_settings():
    """Read ~/.claude/claudectl.json, merged over defaults. Never raises."""
    s = dict(_DEFAULT_SETTINGS)
    try:
        with open(settings_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            s.update({k: v for k, v in data.items() if k in _DEFAULT_SETTINGS})
    except Exception:
        pass
    return s


def save_settings(s):
    """Write settings dict. Returns True on success."""
    try:
        os.makedirs(os.path.dirname(settings_file), exist_ok=True)
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(s, f, indent=2)
        return True
    except Exception:
        return False


# ── executable discovery ────────────────────────────────────

def find_editor():
    """Best available text editor. Settings override > Notepad++ > VS Code > notepad."""
    override = load_settings().get('editor', '')
    if override and os.path.exists(override):
        return override
    candidates = [
        r'C:\Program Files\Notepad++\notepad++.exe',
        r'C:\Program Files (x86)\Notepad++\notepad++.exe',
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Notepad++', 'notepad++.exe'),
        shutil.which('notepad++'),
        shutil.which('code'),
        os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'notepad.exe'),
        shutil.which('notepad'),
    ]
    for exe in candidates:
        if exe and os.path.exists(exe):
            return exe
    return None


def open_in_editor(path):
    """Open path in the best available editor. Returns True if launched."""
    import subprocess
    editor = find_editor()
    if not editor:
        return False
    try:
        subprocess.Popen([editor, path])
        return True
    except Exception:
        return False


def get_claude_exe():
    """Locate claude.exe. Settings override > default install path > PATH. None if missing."""
    override = load_settings().get('claude_exe', '')
    if override and os.path.exists(override):
        return override
    default = os.path.join(_USERPROFILE, '.local', 'bin', 'claude.exe')
    if os.path.exists(default):
        return default
    for name in ('claude.exe', 'claude'):
        found = shutil.which(name)
        if found:
            return found
    return None

# ── ANSI colors ──────────────────────────────────────────────
C_RESET  = '\033[0m'
C_TITLE  = '\033[96m'     # cyan — titles / headers
C_SEL    = '\033[93m'     # yellow — selected > marker
C_DIM    = '\033[90m'     # dark gray — separators, hints, age
C_STAR   = '\033[93m'     # yellow — ★☆ stars
C_GREEN  = '\033[92m'     # green — MCP connected
C_BOLD   = '\033[1m'      # bold
C_SRCH   = '\033[96;1m'   # bright cyan bold — active search bar

BAD_PREFIXES = ('<', '[', 'I0', 'W0', 'E0', 'Caveat', 'Base directory', 'session')
BAD_CONTAINS = ['.claude', 'plugins', 'interrupted by user', 'tool use', 'local-command']
W = 62

EFFORTS       = ['',        'low', 'medium', 'high', 'xhigh', 'max']
EFFORT_LABELS = ['default', 'low', 'medium', 'high', 'xhigh', 'max']
MODELS        = ['',          'haiku-4-5', 'sonnet-4-6', 'opus-4-8', 'fable-5']
MODEL_LABELS  = ['default',   'haiku-4-5', 'sonnet-4-6', 'opus-4-8', 'fable-5']

_AUTOGEN_START  = '<!-- AUTOGEN:START -->'
_AUTOGEN_END    = '<!-- AUTOGEN:END -->'
_SESSIONS_START = '<!-- SESSIONS:START -->'
_SESSIONS_END   = '<!-- SESSIONS:END -->'
_AI_MARKER      = '<!-- AI:ANALYZED -->'

_GMCP_START = '<!-- MCP:{name}:START -->'
_GMCP_END   = '<!-- MCP:{name}:END -->'
