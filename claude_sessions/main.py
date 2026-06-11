import os
import sys
import atexit
import subprocess

from .config import projects_dir, choice_file, global_claude_md
from .config import C_RESET, C_STAR, C_DIM, C_TITLE, C_BOLD
from .config import get_claude_exe, load_settings, save_settings
from .paths import find_actual_path
from .sessions import get_session_info, load_recent_sessions, save_last_session, format_age
from .ui import menu, launch_options_menu, pause, help_screen, settings_menu
from .session_menu import sessions_menu
from .mcp import mcp_status_line, global_claude_md_menu, mcp_servers
from .ui import _cls
from . import render


def run():
    # ── UTF-8 console ─────────────────────────────────────────────
    os.system('chcp 65001 >nul 2>&1')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    # Alternate screen buffer + hidden cursor for the whole TUI session.
    # Restored before claude.exe takes the console (atexit = safety net).
    render.screen_init()
    atexit.register(render.screen_restore)

    # ── claude.exe availability check ─────────────────────────────
    if not get_claude_exe():
        _cls()
        print(f"\n  {C_TITLE}{C_BOLD}claude.exe not found{C_RESET}\n")
        print(f"  claudectl could not locate Claude Code. Checked:")
        print(f"    - %USERPROFILE%\\.local\\bin\\claude.exe")
        print(f"    - PATH (claude / claude.exe)")
        print(f"    - settings override (~/.claude/claudectl.json)\n")
        print(f"  Install Claude Code:  https://docs.anthropic.com/claude-code")
        print(f"  Or set the path in Settings (⚙) after continuing.\n")
        pause("  Press Enter to continue anyway...")

    # ── discover projects ─────────────────────────────────────────

    entries = []
    if os.path.exists(projects_dir):
        for name in os.listdir(projects_dir):
            proj = os.path.join(projects_dir, name)
            if not os.path.isdir(proj):
                continue
            actual = find_actual_path(name)
            if not actual:
                continue
            mtime = os.path.getmtime(proj)
            entries.append((mtime, actual, name))

    entries.sort(reverse=True)

    if not entries:
        _cls()
        print(f"  No Claude sessions found.\n  Scanned: {projects_dir}")
        pause("\n  Press Enter to exit...")
        sys.exit(0)

    W = 62
    project_items = [(f"{os.path.basename(p) or p:<28}  {p}", p) for _, p, _ in entries]

    recent = load_recent_sessions(5)
    if recent:
        qr_items = []
        for i, sess in enumerate(recent):
            lr_proj    = os.path.basename(sess['project_path']) or sess['project_path']
            lr_preview = sess.get('preview', '') or sess['session_id'][:8] + '...'
            lr_age     = format_age(sess['timestamp'])
            star = '★' if i == 0 else '☆'
            label = render.cols(
                [f"{C_STAR}{star}{C_RESET}", lr_proj, lr_preview,
                 f"{C_DIM}({lr_age.strip()}){C_RESET}"],
                [3, 18, None, 7],
                aligns=['left', 'left', 'left', 'right'])
            qr_items.append((label, f"__quickresume_{i}__"))
        full_items = qr_items + [(f"{'─' * W}", None)] + project_items
    else:
        full_items = project_items

    full_items = full_items + [
        (f"{'─' * W}", None),
        ('⚙  Global CLAUDE.md  /  MCP Analysis', '__global_claude_md__'),
        ('⚙  Settings', '__settings__'),
        ('?  Help', '__help__'),
    ]

    # ── main loop ─────────────────────────────────────────────────

    path = encoded_name = proj_folder = choice = None
    effort, model = '', ''

    while True:
        sel = menu(full_items, "SELECT PROJECT", footer_fn=mcp_status_line)
        if not sel:
            sys.exit(0)

        if sel and sel.startswith('__quickresume_'):
            idx  = int(sel[len('__quickresume_'):-2])
            sess = recent[idx]
            path         = sess['project_path']
            encoded_name = sess['encoded_name']
            proj_folder  = os.path.join(projects_dir, encoded_name)
            choice       = f"resume:{sess['session_id']}"

        elif sel == '__global_claude_md__':
            global_claude_md_menu()
            continue

        elif sel == '__settings__':
            settings_menu()
            continue

        elif sel == '__help__':
            help_screen()
            continue

        else:
            path = sel
            encoded_name = next((n for _, p, n in entries if p == path), None)
            proj_folder  = os.path.join(projects_dir, encoded_name) if encoded_name else None

            sessions = []
            if proj_folder and os.path.exists(proj_folder):
                for f in os.listdir(proj_folder):
                    if not f.endswith('.jsonl'):
                        continue
                    fpath = os.path.join(proj_folder, f)
                    mtime = os.path.getmtime(fpath)
                    preview, count = get_session_info(fpath)
                    sessions.append((mtime, f[:-6], preview, count))
                sessions.sort(reverse=True)

            project_name = os.path.basename(path) or path
            choice = sessions_menu(sessions, proj_folder, project_name, path)
            if not choice:
                continue

        # Launch options (skip for terminal); ESC = back to main menu
        if choice == 'terminal':
            break
        settings = load_settings()
        proj_def = settings.get('project_defaults', {}).get(encoded_name or '', {})
        opts = launch_options_menu(
            os.path.basename(path) or path,
            default_effort=proj_def.get('effort', settings.get('default_effort', '')),
            default_model=proj_def.get('model', settings.get('default_model', '')),
        )
        if opts is None:
            choice = None
            continue
        effort, model = opts
        # Remember per-project launch choices for next time
        if encoded_name:
            settings.setdefault('project_defaults', {})[encoded_name] = {
                'effort': effort, 'model': model,
            }
            save_settings(settings)
        break

    # Persist last session for quick-resume (resume/fork only)
    if choice and choice not in ('terminal', 'new'):
        sid = choice.split('::')[1] if '::' in choice else \
              (choice.split(':')[1] if ':' in choice else '')
        if sid:
            save_last_session(path, encoded_name, sid)

    # Validate action format before handing to the bat launcher
    valid = (
        choice in ('terminal', 'new')
        or (choice.startswith('resume:') and len(choice) > 7)
        or (choice.startswith('fork:') and len(choice) > 5)
        or (choice.startswith('resume-named::') and '::' in choice[14:])
    )
    if not valid:
        _cls()
        print(f"\n  Internal error — invalid action: {choice!r}")
        pause("\n  Press Enter to exit...")
        sys.exit(1)
    if '|' in f"{path}{encoded_name}{choice}":
        _cls()
        print(f"\n  Internal error — '|' not allowed in launch data.")
        pause("\n  Press Enter to exit...")
        sys.exit(1)

    # Leave the alt screen before anything else owns the console
    render.screen_restore()

    with open(choice_file, 'w', encoding='utf-8', newline='') as f:
        f.write(f"{path}|{encoded_name}|{choice}|{effort}|{model}\r\n")

    # When run via 'Open Repo cmd.bat' the bat reads the choice file and
    # launches claude itself. When run standalone (pipx / `claudectl`),
    # launch directly from Python.
    if os.environ.get('CLAUDECTL_BAT') != '1':
        _direct_launch(path, encoded_name, choice, effort, model)


def _direct_launch(path, encoded_name, choice, effort, model):
    """Launch claude.exe (or a terminal) directly — used when not started via the bat."""
    from .sessions import read_extra_paths

    render.screen_restore()   # idempotent — console must be clean for claude

    proj_folder = os.path.join(projects_dir, encoded_name) if encoded_name else None

    env = os.environ.copy()
    extra = read_extra_paths(proj_folder)
    if extra:
        env['PATH'] = ';'.join(extra) + ';' + env.get('PATH', '')

    if choice == 'terminal':
        subprocess.call('cmd /k', cwd=path, env=env, shell=True)
        return

    claude = get_claude_exe()
    if not claude:
        _cls()
        print(f"\n  ✘ claude.exe not found — cannot launch.")
        pause("\n  Press Enter to exit...")
        sys.exit(1)

    args = [claude]
    if choice.startswith('resume:'):
        args += ['-r', choice[7:]]
    elif choice.startswith('resume-named::'):
        args += ['-r', choice[14:].split('::', 1)[0]]
    elif choice.startswith('fork:'):
        args += ['-r', choice[5:], '--fork-session']
    # 'new' → no extra args

    if effort:
        args += ['--effort', effort]
    if model:
        args += ['--model', model]
    sp_file = os.path.join(proj_folder, 'system-prompt.txt') if proj_folder else ''
    if sp_file and os.path.exists(sp_file):
        args += ['--system-prompt-file', sp_file]

    _cls()
    print(f"  Location: {path}")
    print(f"  Action:   {choice}")
    print(f"  {'-' * 42}\n")
    try:
        subprocess.call(args, cwd=path, env=env)
    except Exception as e:
        print(f"\n  ✘ Launch failed: {e}")
        pause("\n  Press Enter to exit...")
        sys.exit(1)
