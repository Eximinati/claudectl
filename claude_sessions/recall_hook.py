"""Claude Code UserPromptSubmit hook — inject the task-relevant memory
subgraph as additionalContext. Pure local scoring, <1s; NEVER blocks the
prompt (exit 0 on every failure).

Installed by claudectl (hooks.install_memory_hook) as:
    "<python.exe>" "<this file>"
Runs as a plain script; bootstraps sys.path so the package imports regardless
of install mode.
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _enabled_for(cwd, settings):
    """Global default `memory_prompt_hook`, overridable per project via
    project_defaults[<encoded>]['memory_hook']."""
    try:
        from claude_sessions.paths import encode_component
        enc = encode_component(os.path.abspath(cwd))
        proj = (settings.get('project_defaults') or {}).get(enc) or {}
        if 'memory_hook' in proj:
            return bool(proj['memory_hook'])
    except Exception:
        pass
    return bool(settings.get('memory_prompt_hook', False))


def _prompt_submit(cwd, prompt):
    # cheap gate BEFORE package imports: no graph → no-op
    graph_p = os.path.join(cwd, '.claudectl', 'memory', 'graph.json')
    if not os.path.isfile(graph_p) or not (prompt or '').strip():
        return 0
    from claude_sessions.config import load_settings
    settings = load_settings()
    if not _enabled_for(cwd, settings):
        return 0
    from claude_sessions import recall
    r = recall.retrieve(cwd, None, prompt, settings.get('memory_budget', 600))
    if r['empty']:
        return 0
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": r['text']}}))
    return 0


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(data, dict):
        return 0
    if data.get('hook_event_name') == 'UserPromptSubmit':
        cwd = data.get('cwd') or os.getcwd()
        return _prompt_submit(cwd, data.get('prompt', ''))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)          # never block the user's prompt
