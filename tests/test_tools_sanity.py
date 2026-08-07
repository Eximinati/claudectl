"""Static guards on the verification tools themselves.

A test tool that silently stops executing is worse than no tool: it reports
success. `tools/smoke_gui.py` spent a while in exactly that state — a helper was
inserted at four-space indentation inside `main()`, which closed the
`with sync_playwright()` block around it, so every check below became
unreachable code sitting after a `return` inside that helper. It printed
"FAILURES: none" and ran nothing.

Nothing in the suite could see that, because the suite does not run the tools.
These two checks do the little that can be done statically, and the tools carry
the dynamic half themselves (smoke_gui asserts a floor on how many checks
actually executed).
"""
import ast
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TOOLS = os.path.join(ROOT, 'tools')
PKG = os.path.join(ROOT, 'claude_sessions')


def _py_files(*dirs):
    for d in dirs:
        for fn in sorted(os.listdir(d)):
            if fn.endswith('.py'):
                yield os.path.join(d, fn)


TERMINAL = (ast.Return, ast.Raise, ast.Continue, ast.Break)


def _unreachable(tree):
    """Statements that follow an unconditional return/raise in the same block.

    Not a general dead-code analysis — just the one shape that bit: real work
    left stranded after a terminator, which no linter in this repo runs to
    catch and which reads as perfectly normal code.
    """
    out = []
    for node in ast.walk(tree):
        for field in ('body', 'orelse', 'finalbody'):
            block = getattr(node, field, None)
            if not isinstance(block, list):
                continue
            for i, st in enumerate(block[:-1]):
                if isinstance(st, TERMINAL):
                    nxt = block[i + 1]
                    # a docstring-ish bare expression is harmless noise
                    if isinstance(nxt, ast.Expr) and isinstance(
                            nxt.value, ast.Constant):
                        continue
                    out.append((getattr(nxt, 'lineno', '?'),
                                type(nxt).__name__))
    return out


@pytest.mark.parametrize('path', list(_py_files(TOOLS, PKG)),
                         ids=lambda p: os.path.basename(p))
def test_no_code_is_stranded_after_a_return(path):
    with open(path, encoding='utf-8') as fh:
        tree = ast.parse(fh.read(), path)
    bad = _unreachable(tree)
    assert not bad, f'{os.path.basename(path)}: unreachable after return {bad}'


def test_the_smoke_test_refuses_to_pass_while_running_nothing():
    """The dynamic half of the same guard, asserted to still be present: a
    floor on how many checks executed, so an empty run fails loudly."""
    src = open(os.path.join(TOOLS, 'smoke_gui.py'), encoding='utf-8').read()
    assert 'FLOOR' in src and 'len(ran) < FLOOR' in src
    assert 'ran.append(label)' in src


def test_the_smoke_checks_live_inside_the_browser_block():
    """The specific structural mistake: everything that touches the page must
    be nested under `with sync_playwright()`. If the count of checks indented
    deeper than the `with` collapses, the block closed early again."""
    src = open(os.path.join(TOOLS, 'smoke_gui.py'), encoding='utf-8').read()
    lines = src.splitlines()
    start = next(i for i, l in enumerate(lines) if 'with sync_playwright()' in l)
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].strip() and not lines[i].startswith('        ')),
               len(lines))
    inside = sum(1 for l in lines[start:end] if l.strip().startswith('check('))
    assert inside >= 40, (
        f'only {inside} checks are inside the browser block — the rest are '
        'outside it and will not run')
