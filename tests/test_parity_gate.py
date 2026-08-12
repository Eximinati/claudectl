"""Parity as a gate, not a review.

`test_gui_parity.py` tests what the endpoints DO. Nothing tested that a
counterpart exists at all, which is why drift happened in both directions —
`health.py` was 229 lines and a README headline with no GUI trace, while
`gui-audit.md` listed seventeen routes that had never existed.
"""

import ast
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_sessions import gui, gui_api, session_menu

TESTS = os.path.dirname(os.path.abspath(__file__))


def _routes():
    return (set(gui_api.GET_ROUTES) | set(gui_api.POST_ROUTES)
            | set(gui._LOCAL_GET) | set(gui._LOCAL_POST))


def test_every_tui_action_has_a_gui_counterpart():
    routes = _routes()
    missing = [(k, label, route)
               for k, label, _scope, route in
               session_menu.ACTIONS + session_menu.ARCHIVED_ACTIONS
               if route and route not in routes]
    assert not missing, 'TUI actions with no GUI route: %s' % (missing,)


def test_an_action_without_a_counterpart_must_say_why():
    """A blank route is allowed — some things only make sense in a terminal —
    but it has to be a decision, so the table carries a comment beside it."""
    src = io.open(session_menu.__file__, encoding='utf-8').read()
    table = src[src.index('ACTIONS = ['):src.index('#: actions reachable only')]
    for k, label, _scope, route in session_menu.ACTIONS:
        if route:
            continue
        line = next(ln for ln in table.splitlines() if "'%s'" % label in ln)
        assert '#' in line, 'terminal-only action %r gives no reason' % (label,)


def test_the_action_table_still_drives_the_hints():
    """Hoisting it out of the render loop is what makes the gate possible; if
    the hints stop coming from it, the table is decoration."""
    src = io.open(session_menu.__file__, encoding='utf-8').read()
    assert "_hints('session')" in src and "_hints('project')" in src
    labels = {label for _k, label, _s, _r in session_menu.ACTIONS}
    assert {'view', 'fork', 'review', 'ctx audit'} <= labels


def test_shift_keys_render_as_shift_in_the_hints():
    hints = dict(session_menu._hints('session'))
    assert '⇧F' in hints and hints['⇧F'] == 'files'
    assert 'v' in hints, 'a lowercase key must not grow a shift marker'


# ── endpoint test floor ──────────────────────────────────────

def _tested_routes():
    """Every '/api/...' string literal anywhere in the test suite."""
    found = set()
    for name in os.listdir(TESTS):
        if not name.endswith('.py'):
            continue
        src = io.open(os.path.join(TESTS, name), encoding='utf-8').read()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                v = node.value
                if v.startswith('/api/'):
                    found.add(v.split('?')[0])
    return found


def test_every_endpoint_is_exercised_by_something():
    """Forty-nine routes had no HTTP-level test of any kind — the exact class of
    bug already recorded here: gate['diff'] shipped broken because the only
    gate test covered one of the two shapes its producers passed.

    Coverage comes from two places. Most routes have a test that names them and
    asserts what they return; the rest are covered by the parametrized floor in
    `test_endpoint_floor.py`, which is shallow (it only proves the route does
    not fault) but TOTAL — and total is what stops a new route shipping with
    nothing at all behind it.
    """
    named = _tested_routes()
    covered = named | _floor_routes()
    missing = sorted(_routes() - covered)
    assert not missing, 'endpoints with no test at all: %s' % (missing,)


def _floor_routes():
    """What the parametrized floor covers — read off the same live tables it
    parametrizes over, so the two cannot drift apart."""
    src = io.open(os.path.join(TESTS, 'test_endpoint_floor.py'),
                  encoding='utf-8').read()
    if "_all('GET')" not in src or "_all('POST')" not in src:
        return set()                       # it stopped covering; report nothing
    return _routes()


def test_the_floor_is_driven_by_the_live_route_tables():
    """If the floor is ever given a hardcoded list it stops being a floor — the
    same rot that had smoke_gui checking eleven of twelve pages."""
    src = io.open(os.path.join(TESTS, 'test_endpoint_floor.py'),
                  encoding='utf-8').read()
    assert "@pytest.mark.parametrize('route', _all('GET'))" in src
    assert "@pytest.mark.parametrize('route', _all('POST'))" in src
    assert "getattr(ga, table_name + '_ROUTES')" in src, \
        'the floor stopped reading the live tables'


def test_most_endpoints_have_a_test_that_names_them():
    """The floor proves a route answers; it cannot prove a route is CORRECT.
    This keeps the shallow-but-total check from becoming the only coverage —
    the ratio may not slide below where it stands now."""
    named = _tested_routes() & _routes()
    assert len(named) >= 40, (
        'only %d of %d routes have a test naming them' % (len(named), len(_routes())))


def test_the_api_reference_is_generated_and_current():
    """docs/gui-audit.md was a hand-written route catalogue that had drifted to
    listing seventeen routes which do not exist. A hand-maintained copy of
    something the code already states is a copy that will be wrong."""
    sys.path.insert(0, os.path.join(os.path.dirname(TESTS), 'tools'))
    import gen_api_docs
    current = io.open(gen_api_docs.OUT, encoding='utf-8').read().replace('\r\n', '\n')
    assert current == gen_api_docs.render(), \
        'docs/api.md is stale — run tools/gen_api_docs.py'


def test_the_route_tables_have_no_duplicates_between_them():
    """A path in both a local table and gui_api's is ambiguous — the local one
    silently wins."""
    both = (set(gui._LOCAL_GET) & set(gui_api.GET_ROUTES)) | \
           (set(gui._LOCAL_POST) & set(gui_api.POST_ROUTES))
    assert not both, both
