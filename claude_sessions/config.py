import os

projects_dir = os.path.join(os.environ['USERPROFILE'], '.claude', 'projects')
choice_file = os.environ.get('CHOICE_FILE', os.path.join(os.environ['TEMP'], 'choice_claude.txt'))
last_session_file = os.path.join(projects_dir, 'last-session.json')

global_claude_md = os.path.join(os.environ['USERPROFILE'], '.claude', 'CLAUDE.md')

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
