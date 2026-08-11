"""Insulate the suite from the environment it happens to be run in.

`config.get_config_dir()` resolves `CLAUDE_CONFIG_DIR` env > setting > default,
because claudectl sets that variable when it launches a session under a named
account and everything running inside that session has to agree about which
account it is. The consequence is that running pytest from INSIDE a Claude Code
session inherits the account of whoever is running it — which is exactly how
this file came to exist: the suite was green from a plain shell and red from a
session on a non-default account, in `test_get_config_dir_override`,
`test_get_config_dir_expands` and `test_all_config_dirs_merges_accounts_and_dedups`.

The pop is at MODULE level, not only in the fixture, and that ordering is
load-bearing — mutation-verified, and the split is exact. Removing it leaves
the two `test_config` tests passing, because they call `get_config_dir()` at
test time and the fixture's `delenv` has already run. It leaves
`test_all_config_dirs_merges_accounts_and_dedups` FAILING, because that one
compares against `config.config_dir` — an import-time constant, computed
before any fixture exists. pytest imports conftest before any test module, so
a module-level pop is the only thing that runs early enough to reach it.

The autouse fixture then covers the per-test case; `monkeypatch.setenv` inside a
test still wins, because fixtures run before the test body.
"""
import os

import pytest

#: Ambient Claude Code state that must never reach a test. Cleared at import so
#: the import-time constants in `config` are computed from a clean environment.
_AMBIENT = ('CLAUDE_CONFIG_DIR',)

for _var in _AMBIENT:
    os.environ.pop(_var, None)


@pytest.fixture(autouse=True)
def _no_ambient_claude_env(monkeypatch):
    for var in _AMBIENT:
        monkeypatch.delenv(var, raising=False)
