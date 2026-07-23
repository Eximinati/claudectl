from claude_sessions import config as c
from claude_sessions import omniroute


def test_omniroute_env_disabled_by_default():
    assert c.omniroute_env({}) == {}
    assert c.omniroute_env({'omniroute_exec_model': ''}) == {}


def test_omniroute_env_returns_anthropic_override_when_configured():
    s = {'omniroute_exec_model': 'glm-4.6',
         'omniroute_base_url': 'http://localhost:20128',
         'omniroute_api_key': 'secret-token'}
    env = c.omniroute_env(s)
    assert env == {'ANTHROPIC_BASE_URL': 'http://localhost:20128',
                    'ANTHROPIC_AUTH_TOKEN': 'secret-token',
                    'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1',
                    'CLAUDE_CODE_SUBAGENT_MODEL': 'claude-sonnet-5'}


def test_omniroute_client_degrades_quietly_when_unreachable():
    # no server on this port -- every call must fail closed, never raise
    dead = 'http://127.0.0.1:1'
    assert omniroute.is_reachable(dead, timeout=1) is False
    assert omniroute.list_models(dead) == []
    assert omniroute.provider_status(dead) == {'catalog': 0, 'configured': 0, 'active': 0}


def test_ensure_running_reports_missing_binary(monkeypatch):
    import shutil
    dead = 'http://127.0.0.1:1'
    monkeypatch.setattr(shutil, 'which', lambda name: None)
    ok, msg = omniroute.ensure_running(dead, timeout=1)
    assert ok is False and 'npm install' in msg


def test_ensure_running_skips_start_when_already_up(monkeypatch):
    monkeypatch.setattr(omniroute, 'is_reachable', lambda *a, **k: True)
    ok, msg = omniroute.ensure_running('http://localhost:20128')
    assert (ok, msg) == (True, 'already running')


def test_provider_status_reads_health_endpoint(monkeypatch):
    # confirmed against a live instance: /v1/models lists a static catalog
    # regardless of connected providers -- providerSummary is the real signal
    fake_health = {'providerSummary': {'catalogCount': 257, 'configuredCount': 1,
                                        'activeCount': 1}}
    monkeypatch.setattr(omniroute, '_get', lambda base, path, key, timeout=5: fake_health)
    assert omniroute.provider_status('http://localhost:20128') == \
        {'catalog': 257, 'configured': 1, 'active': 1}


def test_cli_connections_missing_binary_returns_empty(monkeypatch):
    import shutil
    monkeypatch.setattr(shutil, 'which', lambda name: None)
    assert omniroute.cli_connections() == []


def test_cli_connections_parses_providers_list_json(monkeypatch):
    # shape confirmed against a live `omniroute providers list --json`
    fake = {'providers': [{'id': 'abc123', 'provider': 'opencode', 'name': 'OpenCode Account 1',
                           'testStatus': 'error',
                           'lastError': 'Connection OpenCode Account 1 has no API key configured.'}]}
    monkeypatch.setattr(omniroute, '_cli', lambda args, timeout=15: fake)
    conns = omniroute.cli_connections()
    assert conns == [{'id': 'abc123', 'provider': 'opencode', 'name': 'OpenCode Account 1',
                      'status': 'error',
                      'error': 'Connection OpenCode Account 1 has no API key configured.'}]


def test_cli_test_connection_reports_unavailable_cli(monkeypatch):
    monkeypatch.setattr(omniroute, '_cli', lambda args, timeout=15: None)
    ok, msg = omniroute.cli_test_connection('opencode')
    assert ok is False and 'not available' in msg


def test_test_live_unreachable_fails_closed():
    ok, used, msg = omniroute.test_live('http://127.0.0.1:1')
    assert ok is False and used == ''


def test_test_live_reports_routed_model_on_success(monkeypatch):
    # shape confirmed against a live server: auto/coding -> big-pickle via
    # OpenCode, surfaced in the x-omniroute-model/-provider response headers
    class FakeResp:
        headers = {'x-omniroute-model': 'big-pickle', 'x-omniroute-provider': 'oc'}
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(omniroute.urllib.request, 'urlopen', lambda req, timeout=30: FakeResp())
    ok, used, msg = omniroute.test_live('http://localhost:20128', 'auto/coding')
    assert ok is True and used == 'big-pickle' and 'oc' in msg


def test_cli_strips_ansi_log_preamble_before_json(monkeypatch):
    # regression: the CLI prefixes --json output with ANSI-colored log lines,
    # e.g. '\x1b[2m...Loaded env...\x1b[0m\n{...}'. The ANSI escape itself
    # contains a literal '[' that sorts BEFORE the real '{' -- treating '['
    # as a candidate start marker (as an earlier version of this function
    # did) corrupts the parse. Only '{' is a valid start here.
    raw = '  \x1b[2m\U0001f4cb Loaded env from x\x1b[0m\n{"providers": []}\n'

    class FakeCompleted:
        stdout = raw
        stderr = ''
        returncode = 0
    import shutil
    monkeypatch.setattr(shutil, 'which', lambda name: 'omniroute')
    monkeypatch.setattr(omniroute.subprocess, 'run', lambda *a, **k: FakeCompleted())
    assert omniroute._cli(['providers', 'list', '--json']) == {'providers': []}


if __name__ == '__main__':
    test_omniroute_env_disabled_by_default()
    test_omniroute_env_returns_anthropic_override_when_configured()
    test_omniroute_client_degrades_quietly_when_unreachable()
    print('ok')


def test_omniroute_env_with_model_param_bypasses_exec_model_gate():
    """Passing model='_' forces OmniRoute env even when omniroute_exec_model is
    not set — handles the GUI plan-execute modal's via='omniroute' path."""
    s = {'omniroute_base_url': 'http://localhost:20128',
         'omniroute_api_key': 'secret-token'}
    # without model param: empty because exec_model is not set
    assert c.omniroute_env(s) == {}
    # with model param: env vars are returned
    env = c.omniroute_env(s, model='_')
    assert env.get('ANTHROPIC_BASE_URL') == 'http://localhost:20128'
    assert env.get('ANTHROPIC_AUTH_TOKEN') == 'secret-token'


def test_omniroute_env_includes_subagent_model_and_disable_traffic():
    """omniroute_env always sets CLAUDE_CODE_SUBAGENT_MODEL and
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC so agents/skills use Sonnet 5."""
    s = {'omniroute_exec_model': 'auto/coding',
         'omniroute_base_url': 'http://localhost:20128',
         'omniroute_api_key': 'secret'}
    env = c.omniroute_env(s)
    assert env['CLAUDE_CODE_SUBAGENT_MODEL'] == 'claude-sonnet-5'
    assert env['CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC'] == '1'


def test_omniroute_env_filters_empty_values():
    """Empty string values are filtered out so ambient env is never clobbered."""
    s = {'omniroute_exec_model': 'auto/coding',
         'omniroute_base_url': '',
         'omniroute_api_key': ''}
    env = c.omniroute_env(s)
    assert 'ANTHROPIC_BASE_URL' not in env
    assert 'ANTHROPIC_AUTH_TOKEN' not in env


def test_prepare_launch_unknown_model_raises_valueerror(monkeypatch):
    """prepare_launch() raises ValueError for a model not in list_models()."""
    monkeypatch.setattr(omniroute, 'ensure_running', lambda *a, **k: (True, 'running'))
    from claude_sessions.config import load_settings, save_settings
    s = load_settings()
    s['omniroute_base_url'] = 'http://localhost:20128'
    s['omniroute_api_key'] = ''
    s['omniroute_exec_model'] = 'free/x'
    save_settings(s)
    monkeypatch.setattr(omniroute, 'list_models',
                        lambda *a, **k: [('free/x', 'Free Model X'), ('free/y', 'Free Model Y')])
    import pytest
    # 'bogus' is not in the list -> ValueError
    with pytest.raises(ValueError, match='bogus'):
        omniroute.prepare_launch('bogus')
    # 'auto/coding' is always accepted without validation
    env = omniroute.prepare_launch('auto/coding')
    assert isinstance(env, dict)


def test_prepare_launch_ensure_running_failure_propagates(monkeypatch):
    """prepare_launch raises RuntimeError when ensure_running fails."""
    monkeypatch.setattr(omniroute, 'ensure_running',
                        lambda *a, **k: (False, 'daemon dead'))
    import pytest
    with pytest.raises(RuntimeError, match='OmniRoute'):
        omniroute.prepare_launch('auto/coding')
