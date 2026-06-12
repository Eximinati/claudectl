import os
import subprocess
import threading
import time

from .config import W, global_claude_md, get_claude_exe, open_in_editor
from .sessions import get_session_info
from .ui import menu, _cls, pause, run_with_progress


# ── MCP status ────────────────────────────────────────────────

def get_mcp_status():
    """Run 'claude mcp list', return list of (name, status) tuples."""
    claude_exe = get_claude_exe()
    if not claude_exe:
        return []
    try:
        r = subprocess.run(
                [claude_exe, 'mcp', 'list'],
                capture_output=True, text=True, timeout=10,
                stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        lines = (r.stdout + r.stderr).splitlines()
        servers = []
        for line in lines:
            line = line.strip()
            if not line or line.lower().startswith('checking'):
                continue
            if '✔' in line or 'Connected' in line:
                name = line.split(':')[0].strip().replace('claude.ai ', '')
                servers.append((name, 'ok'))
            elif '!' in line or 'auth' in line.lower():
                name = line.split(':')[0].strip().replace('claude.ai ', '')
                servers.append((name, 'auth'))
        return servers
    except Exception:
        return []

mcp_servers = []
_mcp_ready = False

def _mcp_background():
    global mcp_servers, _mcp_ready
    mcp_servers = get_mcp_status()
    _mcp_ready = True

threading.Thread(target=_mcp_background, daemon=True).start()


# ── global CLAUDE.md / MCP analysis ──────────────────────────

def analyze_mcp_tools(mcp_name):
    """Run claude --print to get MCP tool list. Shows progress. Returns markdown string."""
    claude_exe = get_claude_exe()
    if not claude_exe:
        return ''
    prompt = (
        f"Using the {mcp_name} MCP server, call the tools/list endpoint and list every available tool. "
        f"For each tool output: tool name, one-line description, and key parameters. "
        f"Format as markdown. Be concise. No intro text. "
        f"Do not create, write, or edit any files — output the markdown directly."
    )
    # prompt BEFORE --disallowedTools (variadic flag would swallow it)
    out, cancelled = run_with_progress(
        [claude_exe, '--print', prompt,
         '--disallowedTools', 'Write,Edit,NotebookEdit,Bash'],
        ('CLAUDECTL', mcp_name, 'MCP ANALYSIS'),
        f'Analyzing {mcp_name} MCP tools via Claude...  (15-60s)',
        timeout=120)
    if cancelled:
        return ''
    return (out or '').strip()


def update_global_claude_md_mcp(mcp_name, tools_doc):
    """Write/update MCP section in global CLAUDE.md using per-MCP sentinels."""
    start_tag = f'<!-- MCP:{mcp_name}:START -->'
    end_tag   = f'<!-- MCP:{mcp_name}:END -->'
    section   = f"{start_tag}\n## MCP: {mcp_name}\n{tools_doc}\n{end_tag}\n"

    existing = ''
    if os.path.exists(global_claude_md):
        try:
            existing = open(global_claude_md, encoding='utf-8', errors='ignore').read()
        except Exception:
            pass

    if start_tag in existing and end_tag in existing:
        pre  = existing[:existing.index(start_tag)]
        post = existing[existing.index(end_tag) + len(end_tag):]
        final = pre + section + post
    elif existing:
        final = existing.rstrip('\n') + '\n\n' + section
    else:
        final = '# Global Claude Context\n<!-- Edit freely — MCP sections auto-updated -->\n\n' + section

    try:
        with open(global_claude_md, 'w', encoding='utf-8') as f:
            f.write(final)
        return True
    except Exception:
        return False


def global_claude_md_menu():
    """Sub-menu: pick MCP to analyze, or edit global CLAUDE.md."""
    from . import config as _c
    mcp_items = []
    for name, status in mcp_servers:
        icon = f'{_c.C_OK}✔{_c.C_RESET}' if status == 'ok' else f'{_c.C_WARN}!{_c.C_RESET}'
        mcp_items.append((f"{icon}  {name}", f'mcp:{name}'))
    mcp_items += [(f"{'─' * W}", None), ('📝  Edit global CLAUDE.md in editor', '__edit__')]

    while True:
        sel = menu(mcp_items, "GLOBAL CLAUDE.md  /  Select MCP to analyze")
        if not sel:
            return
        if sel == '__edit__':
            if not os.path.exists(global_claude_md):
                with open(global_claude_md, 'w', encoding='utf-8') as f:
                    f.write('# Global Claude Context\n<!-- This file is read by Claude in every session -->\n\n')
            open_in_editor(global_claude_md)
            return
        if sel.startswith('mcp:'):
            mcp_name = sel[4:]
            tools_doc = analyze_mcp_tools(mcp_name)
            if tools_doc:
                ok = update_global_claude_md_mcp(mcp_name, tools_doc)
                _cls()
                if ok:
                    print(f"\n  ✔ Written to {global_claude_md}\n")
                    print(f"  Claude will see {mcp_name} tool docs in every session.\n")
                    open_in_editor(global_claude_md)
                else:
                    print(f"\n  ✘ Failed to write {global_claude_md}\n")
            else:
                _cls()
                print(f"\n  ✘ No output from Claude — MCP may need authentication.\n")
            pause("  Press Enter to continue...")
            return


def mcp_status_line():
    from . import config as _c
    if not _mcp_ready:
        return f'  {_c.C_DIM}MCP: checking...{_c.C_RESET}'
    connected = [name for name, status in mcp_servers if status == 'ok']
    if not connected:
        return ''
    servers = '   '.join(f'{_c.C_OK}✔{_c.C_RESET} {n}' for n in connected)
    return f'  {_c.C_DIM}MCP:{_c.C_RESET} {servers}'
