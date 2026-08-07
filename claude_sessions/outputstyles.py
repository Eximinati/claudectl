"""Output styles — the last unmanaged Claude Code config surface.

An output style replaces the system prompt's "how to behave" section: same
tools, same permissions, different job. Claude Code ships `default`,
`Explanatory` and `Learning`; custom ones are markdown files with YAML
frontmatter in `~/.claude/output-styles/` (user) or `.claude/output-styles/`
(project), selected by `outputStyle` in the corresponding settings.json.

It sits beside skills, agents and hooks in claudectl for one reason worth
stating: it is *per project and per account*, and claudectl is the only thing
here that already knows which project and which account you are launching. A
style that suits a code review is wrong for a refactor, and switching it by
hand in a JSON file is exactly the friction this tool exists to remove.
"""

import os
import re

from . import config as _c

#: shipped with Claude Code; present in the picker, not on disk
BUILTIN = [
    ('default', 'Claude Code as it ships — efficient software engineering.'),
    ('Explanatory', 'Explains its reasoning and the codebase as it works.'),
    ('Learning', 'Collaborative: asks you to write pieces of the code.'),
]

_FM = re.compile(r'^---\s*\n(.*?)\n---\s*\n?', re.S)


def _dirs(project_path=None, cfgdir=None):
    """[(scope, dir)] — user first, project second (project wins in the UI)."""
    out = [('user', os.path.join(cfgdir or _c.config_dir, 'output-styles'))]
    if project_path:
        out.append(('project',
                    os.path.join(project_path, '.claude', 'output-styles')))
    return out


def _parse(path):
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            text = fh.read()
    except OSError:
        return None
    m = _FM.match(text)
    meta, body = {}, text
    if m:
        body = text[m.end():]
        for line in m.group(1).splitlines():
            k, _, v = line.partition(':')
            if _:
                meta[k.strip()] = v.strip().strip('"\'')
    name = meta.get('name') or os.path.splitext(os.path.basename(path))[0]
    return {'name': name,
            'description': meta.get('description', ''),
            'file': path,
            'body': body.strip(),
            'lines': body.count('\n') + 1}


def listing(project_path=None, cfgdir=None):
    """Built-ins plus every custom style, with the active one marked."""
    active = current(project_path, cfgdir)
    styles = [{'name': n, 'description': d, 'file': '', 'builtin': True,
               'scope': 'built-in', 'lines': 0} for n, d in BUILTIN]
    for scope, d in _dirs(project_path, cfgdir):
        try:
            names = sorted(os.listdir(d))
        except OSError:
            continue
        for fn in names:
            if not fn.endswith('.md'):
                continue
            s = _parse(os.path.join(d, fn))
            if s:
                s.pop('body', None)
                s.update(builtin=False, scope=scope)
                styles.append(s)
    for s in styles:
        s['active'] = (s['name'] == active)
    return styles


def _settings_path(project_path=None, cfgdir=None):
    if project_path:
        return os.path.join(project_path, '.claude', 'settings.json')
    return os.path.join(cfgdir or _c.config_dir, 'settings.json')


def _load(path):
    import json
    try:
        with open(path, encoding='utf-8') as fh:
            return json.load(fh) or {}
    except Exception:
        return {}


def current(project_path=None, cfgdir=None):
    """The style in force: project settings shadow user settings."""
    if project_path:
        v = _load(_settings_path(project_path)).get('outputStyle')
        if v:
            return v
    return _load(_settings_path(None, cfgdir)).get('outputStyle') or 'default'


def select(name, project_path=None, cfgdir=None):
    """Write `outputStyle` into the right settings.json, preserving the rest.

    A read-modify-write of a file Claude Code owns: every other key is carried
    through untouched, and `default` clears the key instead of pinning a value
    that is really "no override".
    """
    import json
    path = _settings_path(project_path, cfgdir)
    data = _load(path)
    if name == 'default':
        data.pop('outputStyle', None)
    else:
        data['outputStyle'] = name
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(data, fh, indent=2)
    except OSError as e:
        return False, f'Could not write {path}: {e}'
    where = 'this project' if project_path else 'all projects'
    return True, f'Output style for {where}: {name}'


def read(name, project_path=None, cfgdir=None):
    """The full markdown of a custom style, or '' for a built-in."""
    for _scope, d in _dirs(project_path, cfgdir):
        for fn in (f'{name}.md', f'{name.lower()}.md'):
            p = os.path.join(d, fn)
            if os.path.isfile(p):
                s = _parse(p)
                if s:
                    return s['body']
    return ''


def save(name, description, body, project_path=None, cfgdir=None):
    """Create or overwrite a custom style."""
    slug = re.sub(r'[^A-Za-z0-9_.-]+', '-', name).strip('-')
    if not slug:
        return False, 'A name is required'
    scope_dir = _dirs(project_path, cfgdir)[-1 if project_path else 0][1]
    path = os.path.join(scope_dir, f'{slug}.md')
    text = (f'---\nname: {name}\ndescription: {description}\n---\n\n'
            f'{body.strip()}\n')
    try:
        os.makedirs(scope_dir, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
    except OSError as e:
        return False, str(e)
    return True, f'Saved {slug}.md'


def delete(name, project_path=None, cfgdir=None):
    """Remove a custom style. Built-ins are not on disk and cannot go."""
    if name in [n for n, _d in BUILTIN]:
        return False, f'{name} ships with Claude Code — nothing to delete'
    for _scope, d in _dirs(project_path, cfgdir):
        p = os.path.join(d, f'{name}.md')
        if os.path.isfile(p):
            try:
                os.remove(p)
            except OSError as e:
                return False, str(e)
            return True, f'Deleted {name}'
    return False, f'{name} not found'
