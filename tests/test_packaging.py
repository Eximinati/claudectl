"""Packaging invariants that only a real install can prove.

`pip install claudectl` shipped an empty skills_templates/ for its whole life:
package-data globbed `skills_templates/*.md` while every file is one level
deeper at `skills_templates/<name>/SKILL.md`. CI's import smoke check could not
catch it, because it runs from the source tree where the files are simply there.

The wheel build itself is a CI job (it needs `build`); what runs here is the
cheap half — that the declared globs actually match the files on disk, and that
the console-script target does not drag in the heavy import chain.
"""

import ast
import os
import subprocess
import sys
from glob import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, 'claude_sessions')


def _package_data_globs():
    """The package-data patterns, read out of pyproject without a TOML parser
    dependency (tomllib is 3.11+, this package supports 3.10)."""
    text = open(os.path.join(ROOT, 'pyproject.toml'), encoding='utf-8').read()
    start = text.index('[tool.setuptools.package-data]')
    body = text[start:]
    body = body[body.index('claude_sessions = ['):]
    body = body[:body.index(']') + 1]
    import re
    return re.findall(r'"([^"]+)"', body)


def test_every_declared_glob_matches_at_least_one_file():
    """A glob that matches nothing is invisible: the build succeeds, the wheel is
    just missing the data."""
    empty = [pat for pat in _package_data_globs()
             if not glob(os.path.join(PKG, pat.replace('/', os.sep)))]
    assert not empty, 'package-data patterns matching no files: %s' % empty


def test_the_bundled_skill_templates_are_covered_by_a_glob():
    from claude_sessions import skills
    on_disk = glob(os.path.join(skills.bundled_templates_dir(), '*', 'SKILL.md'))
    assert on_disk, 'no bundled templates on disk — fixture assumption broken'
    covered = set()
    for pat in _package_data_globs():
        covered.update(glob(os.path.join(PKG, pat.replace('/', os.sep))))
    missing = [p for p in on_disk if p not in covered]
    assert not missing, 'templates that would not ship: %s' % missing


def test_the_console_script_target_exists_and_is_thin():
    """`claudectl statusline` runs on every conversation turn. main's import
    chain pulls urllib/ssl/http.client via `usage`; cli.py must dispatch before
    that, exactly as __main__.py does."""
    text = open(os.path.join(ROOT, 'pyproject.toml'), encoding='utf-8').read()
    assert 'claudectl = "claude_sessions.cli:run"' in text

    from claude_sessions import cli
    assert callable(cli.run)

    tree = ast.parse(open(os.path.join(PKG, 'cli.py'), encoding='utf-8').read())
    module_level = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert [a.name for n in module_level for a in n.names] == ['sys'], \
        'cli.py must not import anything heavy at module level'


def test_statusline_via_the_console_script_path_stays_light():
    """The regression this guards: pointing the script at main:run loaded 157
    modules including ssl, on every turn."""
    probe = (
        "import sys;"
        "sys.argv=['claudectl','statusline'];"
        "import claude_sessions.cli as c;"
        "print('ssl' in sys.modules, 'urllib.request' in sys.modules)"
    )
    r = subprocess.run([sys.executable, '-c', probe], capture_output=True,
                       text=True, encoding='utf-8', errors='ignore', timeout=60,
                       cwd=ROOT)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == 'False False', r.stdout
