"""Gates for the MkDocs site.

None of these need mkdocs installed — they read text files only, so they ride the
existing `test` job across the whole OS/Python matrix. `mkdocs build --strict`
in the `docs` job covers what actually needs the toolchain.
"""
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, 'docs')
SITE_URL = 'https://claudectl.space/'

# Moved to notes/ so they are outside docs_dir. Inside it they would be built and
# listed in sitemap.xml even without a nav entry.
INTERNAL_NOTES = ('gui-rework-notes.md', 'plan-execute-audit.md', 'research-2026-08.md')


def _read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def _mkdocs():
    return _read(os.path.join(ROOT, 'mkdocs.yml'))


def _nav_pages():
    """Filenames in the nav block. Regex, not PyYAML — the `test` job installs
    only pytest, the same reason test_packaging.py hand-scans pyproject.toml."""
    return set(re.findall(r':\s*([\w./-]+\.md)\s*$', _mkdocs(), re.M))


def _doc_pages():
    out = set()
    for dirpath, _dirs, files in os.walk(DOCS):
        for name in files:
            if name.endswith('.md'):
                rel = os.path.relpath(os.path.join(dirpath, name), DOCS)
                out.add(rel.replace(os.sep, '/'))
    return out


def test_every_snippet_a_page_pulls_in_resolves():
    """A page including `--8<-- "FILE:section"` renders EMPTY when the marker
    moves — no error, no broken link, nothing for --strict to catch.

    This used to assert the source was always README.md, back when the README WAS
    the site and every page was a nine-line include stub. That direction is
    inverted now (the pages hold the content and the README points at them), so
    the gate is stated against whatever file an include actually names —
    today only docs/changelog.md, pulling the root CHANGELOG.md."""
    for rel in _doc_pages():
        for src, section in re.findall(r'--8<--\s+"([^":]+)(?::([\w-]+))?"',
                                       _read(os.path.join(DOCS, rel))):
            path = os.path.join(ROOT, src.replace('/', os.sep))
            assert os.path.isfile(path), '%s includes missing %s' % (rel, src)
            if section:
                text = _read(path)
                assert '[start:%s]' % section in text, \
                    '%s wants %s:%s — no start marker' % (rel, src, section)
                assert '[end:%s]' % section in text, \
                    '%s wants %s:%s — no end marker' % (rel, src, section)


# The H2s that moved out to their own pages. A reader who lands on the repo should
# see the pitch; the manual is the site's job.
MOVED_OUT = ('## Features', '## Install', '## Usage', '## Reference',
             '## Troubleshooting')


def test_the_readme_stays_a_pitch_and_does_not_grow_back_into_a_manual():
    """It was 907 lines — Features + Install + Usage + Reference alone were 78% of
    it, and someone evaluating the repo had to scroll a manual to find out what it
    was. Nothing stops that creeping back one section at a time, which is what this
    counts."""
    readme = _read(os.path.join(ROOT, 'README.md'))
    lines = len(readme.splitlines())
    assert lines < 200, 'README is %d lines — the manual is moving back in' % lines
    back = [h for h in MOVED_OUT if h in readme]
    assert not back, 'these belong on the docs site, not the README: %s' % back


def test_every_docs_page_the_readme_links_to_exists():
    """The README is now a map. Absolute site URLs are invisible to
    `mkdocs build --strict`, so a page renamed here 404s in production with
    nothing failing anywhere."""
    readme = _read(os.path.join(ROOT, 'README.md'))
    slugs = set(re.findall(re.escape(SITE_URL) + r'([\w-]+)/', readme))
    assert slugs, 'the README stopped pointing at the docs site'
    missing = [s for s in sorted(slugs) if s + '.md' not in _doc_pages()]
    assert not missing, 'README links at missing pages: %s' % missing


def test_no_internal_dev_note_sits_inside_the_docs_dir():
    """docs_dir is the whole of docs/, so anything dropped in it is published."""
    for name in INTERNAL_NOTES:
        assert not os.path.exists(os.path.join(DOCS, name)), \
            '%s is inside docs_dir and would be published' % name
        assert os.path.isfile(os.path.join(ROOT, 'notes', name)), \
            '%s vanished instead of moving to notes/' % name


def test_every_markdown_page_under_docs_is_in_the_nav():
    """The cost of sharing docs_dir with generated output: a stray .md is a live
    public page. Being absent from nav does not stop it building or being
    sitemapped, so require every page to be declared."""
    assert _doc_pages() == _nav_pages(), \
        'nav and docs/ disagree: %s' % sorted(_doc_pages() ^ _nav_pages())


def test_the_nav_only_references_pages_that_exist():
    for page in _nav_pages():
        assert os.path.isfile(os.path.join(DOCS, page)), 'nav points at missing %s' % page


def test_site_url_is_set_because_canonicals_and_the_sitemap_derive_from_it():
    assert 'site_url: %s' % SITE_URL in _mkdocs()
    assert SITE_URL in _read(os.path.join(DOCS, 'robots.txt'))


def test_the_site_sources_are_tracked_by_git():
    """A page that exists locally but was never committed builds fine here and
    404s in production. Same failure the plugin bundle already guards against."""
    want = [os.path.join('docs', 'index.md'), os.path.join('docs', 'faq.md'),
            os.path.join('docs', 'compare.md'), os.path.join('mkdocs.yml'),
            os.path.join('overrides', 'main.html'),
            os.path.join('docs', 'stylesheets', 'extra.css'),
            os.path.join('docs', 'assets', 'favicon.ico'),
            os.path.join('docs', 'assets', 'og-card.png')]
    r = subprocess.run(['git', 'check-ignore'] + want, cwd=ROOT,
                       capture_output=True, text=True, encoding='utf-8',
                       errors='ignore', timeout=60)
    assert r.returncode != 0, 'gitignored site files: %s' % r.stdout
    for rel in want:
        assert os.path.isfile(os.path.join(ROOT, rel)), rel


def test_the_docs_toolchain_stays_out_of_the_shipped_package():
    """Zero runtime dependencies is a marketed claim. mkdocs belongs to
    requirements-docs.txt, the way ruff/build/playwright belong to their CI job."""
    pyproject = _read(os.path.join(ROOT, 'pyproject.toml'))
    assert 'mkdocs' not in pyproject.lower()
    assert not re.search(r'^dependencies\s*=', pyproject, re.M)
    assert 'mkdocs-material' in _read(os.path.join(ROOT, 'requirements-docs.txt'))
