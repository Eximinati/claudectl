"""Claude-powered persistent project memory (native cognee-style ECL).

Builds and stores a semantic knowledge graph of a project — entities and
relationships extracted by Claude (claude.exe) from source files, CLAUDE.md,
and session summaries — under <project>/.claudectl/memory/. Updated
incrementally via file hashes. Powers the semantic layer of the connections
graph and a grounded "ask the project" query. No third-party deps, no separate
API key (reuses Claude Code's auth). Best-effort: failures never corrupt the
stored graph.

Inspired by cognee (Apache-2.0); implemented from scratch.
"""

import os
import json

from . import config as _c

SCHEMA_VERSION = 1
MEM_SUBDIR = os.path.join('.claudectl', 'memory')
GRAPH_NAME = 'graph.json'
PER_FILE_CHARS = 4000    # cap content per file
PER_BATCH_CHARS = 40000  # cap corpus per repo/module Claude call
MODULE_MAX_FILES = 24    # representative files per module
EXTRACT_TIMEOUT = 300


# ── persistence ──────────────────────────────────────────────

def _mem_dirs(project_path, proj_folder):
    out = []
    if project_path:
        out.append(os.path.join(project_path, MEM_SUBDIR))
    if proj_folder:
        out.append(os.path.join(proj_folder, MEM_SUBDIR))
    return out


def _empty():
    return {'schema_version': SCHEMA_VERSION, 'generated_at': '',
            'entities': [], 'relations': [], 'summaries': {}, 'provenance': {}}


def _migrate(m):
    base = _empty()
    for k, v in base.items():
        m.setdefault(k, v)
    m['schema_version'] = SCHEMA_VERSION
    return m


def load_memory(project_path, proj_folder=None):
    for d in _mem_dirs(project_path, proj_folder):
        p = os.path.join(d, GRAPH_NAME)
        if os.path.isfile(p):
            try:
                with open(p, encoding='utf-8') as f:
                    data = json.load(f)
                return _migrate(data) if isinstance(data, dict) else _empty()
            except Exception:
                return _empty()
    return _empty()


def save_memory(project_path, proj_folder, m):
    for d in _mem_dirs(project_path, proj_folder):
        try:
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, GRAPH_NAME), 'w', encoding='utf-8') as f:
                json.dump(m, f, indent=2)
            return True
        except Exception:
            continue
    return False


def clear_memory(project_path, proj_folder=None):
    for d in _mem_dirs(project_path, proj_folder):
        p = os.path.join(d, GRAPH_NAME)
        if os.path.isfile(p):
            try:
                os.remove(p)
            except Exception:
                pass


# ── Claude calls (monkeypatched in tests) ────────────────────

def _claude_stdin(prompt, cwd, timeout=EXTRACT_TIMEOUT,
                  crumbs=('CLAUDECTL', 'MEMORY'), label='Working with Claude...'):
    """Run `claude -p` reading the prompt from stdin (avoids the Windows
    command-line length limit) with a visible progress bar (ESC cancels).
    Returns stdout text or ''."""
    from .config import get_claude_exe
    from .ui import run_with_progress_stdin
    exe = get_claude_exe()
    if not exe:
        return ''
    out, _cancelled = run_with_progress_stdin(
        [exe, '-p', '--disallowedTools', 'Write,Edit,NotebookEdit,Bash'],
        prompt, crumbs, label, timeout=timeout, cwd=cwd)
    return out or ''


def _parse_json(text):
    if not text:
        return None
    t = text.strip()
    if '```' in t:                       # strip code fences
        import re
        m = re.search(r'```(?:json)?\s*(.*?)```', t, re.S)
        if m:
            t = m.group(1).strip()
    if '{' in t and '}' in t:
        t = t[t.index('{'):t.rindex('}') + 1]
    try:
        return json.loads(t)
    except Exception:
        return None


def _extract(corpus_text, cwd, unit='', progress=''):
    """Claude → {summary, entities:[{name,type,summary}], relations:[{source,target,rel}]}
    for one repo/module unit."""
    prompt = (
        "You are building a knowledge graph for a software project module. From "
        "the MODULE CONTENT below, extract: a one-sentence summary of what this "
        f"module ({unit or 'module'}) does, its key entities (components, "
        "services, data models, concepts), and relationships between them.\n\n"
        "Output ONLY valid JSON, no prose, no code fences:\n"
        '{"summary":"one sentence","entities":[{"name":"...",'
        '"type":"module|component|concept|service|model","summary":"one concise sentence"}],'
        '"relations":[{"source":"EntityName","target":"EntityName","rel":"uses|calls|depends_on|contains|implements"}]}\n\n'
        "At most ~15 entities. Use entity NAMES (not ids) in relations.\n\n"
        f"MODULE CONTENT:\n{corpus_text}"
    )
    label = f"Analyzing {unit} with Claude...  {progress}".strip()
    data = _parse_json(_claude_stdin(
        prompt, cwd, crumbs=('CLAUDECTL', 'MEMORY', unit or 'EXTRACT'), label=label))
    if not isinstance(data, dict):
        return {'summary': '', 'entities': [], 'relations': []}
    return {'summary': data.get('summary', '') or '',
            'entities': data.get('entities', []) or [],
            'relations': data.get('relations', []) or []}


def _answer(context, question, cwd):
    prompt = (
        "Answer the QUESTION about this project using ONLY the knowledge-graph "
        "CONTEXT below (entities, relationships, file summaries). Be concise and "
        "specific; if the context is insufficient, say so.\n\n"
        f"CONTEXT:\n{context}\n\nQUESTION: {question}\n"
    )
    return _claude_stdin(prompt, cwd, timeout=120,
                         crumbs=('CLAUDECTL', 'ASK'),
                         label='Asking Claude about the project...').strip()


# ── corpus / units (whole-project coverage) ──────────────────

_EXCLUDE_NAMES = {'claude.md', 'claude.local.md'}
_INTERFACE_HINTS = ('interface', 'api', 'service', 'controller', 'main', 'program',
                    'index', '__init__', 'module', 'core', 'manager', 'model', 'repository')


def _rel(root, f):
    try:
        return os.path.relpath(f, root).replace('\\', '/')
    except Exception:
        return os.path.basename(f)


def _units(project_path, proj_folder):
    """Whole project split into (repo, module, [abs files]) units — every repo
    and its modules, ordered most-important (most files) first."""
    from . import connections
    root = os.path.abspath(project_path)
    files, _ = connections._walk_source_files(root, connections.GROUP_MAX_FILES)
    files = [f for f in files if os.path.basename(f).lower() not in _EXCLUDE_NAMES]
    repos = connections._discover_repos(root, proj_folder)
    rsorted = sorted((os.path.abspath(p) for p in repos), key=len, reverse=True)
    groups = {}
    for f in files:
        repo = connections._cluster_of(f, root, rsorted)
        parts = _rel(root, f).split('/')
        module = parts[1] if len(parts) > 2 else '(root)'
        groups.setdefault((repo, module), []).append(f)
    units = sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True)
    return [(r, m, fs) for (r, m), fs in units]


def _representative(files):
    """Pick the most informative files of a module (interfaces/headers/entry +
    largest), capped, so a module is covered without sending everything."""
    def score(f):
        b = os.path.basename(f).lower()
        s = 5 if any(k in b for k in _INTERFACE_HINTS) else 0
        if os.path.splitext(b)[1] in ('.h', '.hpp', '.cs', '.ts', '.py', '.go'):
            s += 2
        try:
            s += min(os.path.getsize(f) // 2500, 6)
        except OSError:
            pass
        return s
    return sorted(files, key=score, reverse=True)[:MODULE_MAX_FILES]


def _unit_corpus(root, files):
    parts, total = [], 0
    for f in files:
        rel = _rel(root, f)
        piece = f"### FILE: {rel}\n{_read(f)[:PER_FILE_CHARS]}"
        if total + len(piece) > PER_BATCH_CHARS:
            break
        parts.append(piece)
        total += len(piece)
    return '\n\n'.join(parts)


def _read(f):
    try:
        with open(f, encoding='utf-8', errors='ignore') as fh:
            return fh.read()
    except Exception:
        return ''


# ── refresh (cognify) — per repo/module, whole project ───────

def refresh_memory(project_path, proj_folder, project_name):
    """(Re)extract the semantic graph across EVERY repo and its important
    modules. Incremental by file hash; only changed modules are re-analyzed."""
    from .workspace import _sha256_file
    from .config import load_settings
    root = os.path.abspath(project_path)
    mem = load_memory(project_path, proj_folder)
    prov = mem.get('provenance', {})
    units = _units(project_path, proj_folder)

    cur_hashes = {}
    todo = []
    for repo, module, fs in units:
        h = {_rel(root, f): _sha256_file(f) for f in fs}
        cur_hashes.update(h)
        if any(prov.get(rel, {}).get('hash') != hv for rel, hv in h.items()):
            todo.append((repo, module, fs))
    deleted = [rel for rel in prov if rel not in cur_hashes]
    if not todo and not deleted and mem.get('entities'):
        return mem

    max_calls = load_settings().get('memory_max_calls') or None
    if max_calls:
        todo = todo[:max_calls]

    touched_units = {(r, m) for r, m, _ in todo}
    current_units = {(r, m) for r, m, _ in units}          # units that still exist
    current_strs = {f"{r}/{m}" for r, m in current_units}
    # keep entities only for still-existing, un-retouched units
    kept = [e for e in mem.get('entities', [])
            if (e.get('repo'), e.get('module')) in current_units
            and (e.get('repo'), e.get('module')) not in touched_units]
    summaries = {u: s for u, s in mem.get('summaries', {}).items() if u in current_strs}
    relations = [r for r in mem.get('relations', []) if r.get('unit') in current_strs]

    n = len(todo)
    for i, (repo, module, fs) in enumerate(todo):
        unit = f"{repo}/{module}"
        # remove stale summary/relations of this unit
        summaries.pop(unit, None)
        relations = [r for r in relations if r.get('unit') != unit]
        corpus = _unit_corpus(root, _representative(fs))
        if not corpus.strip():
            continue
        ex = _extract(corpus, root, unit=unit, progress=f"({i + 1}/{n})")
        if ex.get('summary'):
            summaries[unit] = ex['summary']
        rel0 = _rel(root, fs[0])
        for e in ex['entities']:
            name = e.get('name')
            if not name:
                continue
            kept.append({'id': f"entity:{repo}:{module}:{name}", 'name': name,
                         'type': e.get('type', 'concept'), 'summary': e.get('summary', ''),
                         'repo': repo, 'module': module, 'source_files': [rel0]})
        names = {e.get('name') for e in ex['entities']}
        for r in ex['relations']:
            if r.get('source') in names and r.get('target') in names:
                relations.append({'source': r['source'], 'target': r['target'],
                                  'rel': r.get('rel', 'relates'), 'unit': unit})

    mem.update({'entities': kept, 'relations': relations, 'summaries': summaries,
                'provenance': {rel: {'hash': h} for rel, h in cur_hashes.items()},
                'generated_at': _iso()})
    save_memory(project_path, proj_folder, mem)
    sync_to_claudemd(project_path, proj_folder, mem)
    try:
        from . import workspace
        workspace.update_manifest(project_path, proj_folder, 'memory')
    except Exception:
        pass
    return mem


def _iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ── digest → CLAUDE.md ───────────────────────────────────────

def build_digest(mem, per_module=10):
    """Project memory map for CLAUDE.md — structured by repo → module, covering
    every analyzed area (not a single global top-N slice)."""
    ents = mem.get('entities', [])
    summaries = mem.get('summaries', {})
    if not ents and not summaries:
        return "_(no semantic memory yet — open the project, press n → m to build it)_"

    # group entities by repo → module
    by_repo = {}
    for e in ents:
        by_repo.setdefault(e.get('repo', '?'), {}).setdefault(e.get('module', '(root)'), []).append(e)
    # repos ordered by total entity count (most significant first)
    repos = sorted(by_repo, key=lambda r: sum(len(v) for v in by_repo[r].values()), reverse=True)

    out = []
    for repo in repos:
        out.append(f"### {repo}")
        mods = by_repo[repo]
        for module in sorted(mods, key=lambda m: len(mods[m]), reverse=True):
            unit = f"{repo}/{module}"
            head = f"**{module}**"
            summ = summaries.get(unit, '').strip()
            out.append(head + (f" — {summ}" if summ else ''))
            for e in mods[module][:per_module]:
                s = e.get('summary', '').strip()
                out.append(f"- {e['name']}" + (f" — {s}" if s else ''))
            if len(mods[module]) > per_module:
                out.append(f"- …(+{len(mods[module]) - per_module} more)")
        out.append('')
    return '\n'.join(out).strip()


def sync_to_claudemd(project_path, proj_folder, mem):
    """Write the memory digest into CLAUDE.md (sentinel block) if enabled."""
    from .config import load_settings
    if not load_settings().get('memory_to_claudemd', True):
        return
    try:
        from .claude_md import write_memory_block
        from . import diffview
        ok, old, new = write_memory_block(project_path, build_digest(mem))
        if ok and old != new:
            diffview.record(project_path, proj_folder, 'claude_md', old, new)
    except Exception:
        _c.log.exception('memory: claude.md sync failed')


# ── ask (search / GRAPH_COMPLETION analogue) ─────────────────

def _tokens(s):
    import re
    return set(re.findall(r'[a-z0-9]+', (s or '').lower()))


def ask_memory(project_path, proj_folder, question, top_k=12):
    mem = load_memory(project_path, proj_folder)
    ents = mem.get('entities', [])
    if not ents:
        return "No project memory yet — build it first (press 'm' in the connections screen)."
    qtok = _tokens(question)
    scored = []
    for e in ents:
        et = _tokens(e.get('name', '')) | _tokens(e.get('summary', ''))
        scored.append((len(qtok & et), e))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [e for s, e in scored[:top_k]] or ents[:top_k]
    names = {e['name'] for e in top}
    rels = [r for r in mem.get('relations', [])
            if r.get('source') in names or r.get('target') in names]
    ctx = ["ENTITIES:"]
    for e in top:
        ctx.append(f"- {e['name']} ({e.get('type', '')}): {e.get('summary', '')}"
                   + (f"  [files: {', '.join(e.get('source_files', []))}]" if e.get('source_files') else ''))
    ctx.append("\nRELATIONSHIPS:")
    for r in rels[:60]:
        ctx.append(f"- {r['source']} —{r.get('rel', '')}→ {r['target']}")
    return _answer('\n'.join(ctx), question, os.path.abspath(project_path)) or "(no answer)"
