"""Cross-project convention memory — the one memory layer that spans ALL
projects. Preference/correction lessons that recur across repos (or are pinned)
are promoted into a small block in the user-level ~/.claude/CLAUDE.md, so a
convention learned in one project ("this machine uses PowerShell 5.1", "prefer
pytest") is remembered everywhere. Token-frugal (≤ ~200 tok), fully automatic.
"""

import os
import json

from . import config as _c
from .memory import _tokens, tokens_estimate

MAX_CONVENTIONS = 12
MAX_TOKENS = 220
_KINDS = ('preference', 'correction')


def _iter_project_graphs():
    """Yield (enc, graph dict) for every project. save_memory mirrors the graph
    into the encoded projects folder, so scan there. Best-effort."""
    projects = _c.projects_dir
    if not os.path.isdir(projects):
        return
    for enc in os.listdir(projects):
        p = os.path.join(projects, enc, '.claudectl', 'memory', 'graph.json')
        if not os.path.isfile(p):
            continue
        try:
            with open(p, encoding='utf-8') as f:
                d = json.load(f)
            if isinstance(d, dict) and d.get('entities'):
                yield enc, d
        except Exception:
            continue


def collect_conventions():
    """Preference/correction lessons that are pinned OR recur across ≥2
    projects. Deduped by summary token-Jaccard. Returns [(summary, score)]."""
    seen = []          # [(tokenset, summary, projects:set, pinned:bool, conf)]
    for enc, g in _iter_project_graphs():
        for e in g.get('entities', []):
            if e.get('type') != 'lesson' or e.get('kind') not in _KINDS:
                continue
            if e.get('status') not in ('approved', 'pinned'):
                continue
            summ = (e.get('summary') or '').strip()
            if not summ:
                continue
            tk = _tokens(summ)
            hit = None
            for rec in seen:
                inter = len(tk & rec[0])
                union = len(tk | rec[0]) or 1
                if inter / union > 0.6:
                    hit = rec
                    break
            if hit:
                hit[2].add(enc)
                if e.get('status') == 'pinned':
                    hit[3] = True
                hit[4] = max(hit[4], e.get('confidence', 0))
            else:
                seen.append([tk, summ, {enc}, e.get('status') == 'pinned',
                             e.get('confidence', 0)])
    out = []
    for _tk, summ, projs, pinned, conf in seen:
        if pinned or len(projs) >= 2:
            score = len(projs) * 10 + (5 if pinned else 0) + conf
            out.append((summ, score))
    out.sort(key=lambda x: -x[1])
    return out[:MAX_CONVENTIONS]


def build_block():
    convs = collect_conventions()
    if not convs:
        return ''
    lines = ["## Conventions (claudectl — learned across your projects)"]
    for summ, _score in convs:
        line = f"- {summ}"
        if tokens_estimate('\n'.join(lines + [line])) > MAX_TOKENS:
            break
        lines.append(line)
    return '\n'.join(lines)


def sync_to_global():
    """Write/replace the CONVENTIONS block in ~/.claude/CLAUDE.md. Only that
    block is touched. Returns True if written. Gated by conventions_to_global."""
    from .config import load_settings, _CONV_START, _CONV_END, global_claude_md
    if not load_settings().get('conventions_to_global', True):
        return False
    block_body = build_block()
    old = ''
    if os.path.isfile(global_claude_md):
        try:
            old = open(global_claude_md, encoding='utf-8', errors='ignore').read()
        except Exception:
            old = ''
    if not block_body:
        # nothing to promote — strip any existing block, leave the rest
        if _CONV_START in old and _CONV_END in old:
            new = (old[:old.index(_CONV_START)]
                   + old[old.index(_CONV_END) + len(_CONV_END):]).rstrip('\n') + '\n'
        else:
            return False
    else:
        section = f"{_CONV_START}\n{block_body}\n{_CONV_END}\n"
        if _CONV_START in old and _CONV_END in old:
            new = (old[:old.index(_CONV_START)] + section
                   + old[old.index(_CONV_END) + len(_CONV_END):])
        elif old.strip():
            new = old.rstrip('\n') + '\n\n' + section
        else:
            new = section
    if new == old:
        return True
    try:
        os.makedirs(os.path.dirname(global_claude_md), exist_ok=True)
        with open(global_claude_md, 'w', encoding='utf-8') as f:
            f.write(new)
        return True
    except Exception:
        _c.log.exception('conventions: global write failed')
        return False
