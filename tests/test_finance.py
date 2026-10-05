import json
import sys
import time
from integrations.hermes.finance import FinancialTools
from integrations.hermes.policy import BASE_TOOLS


ARGS = dict(symbol='AAPL',start='2025-01-01',end='2025-02-01')


def test_financial_tools_are_discoverable_and_reject_untrusted_arguments():
    assert {'trading_price_history','trading_indicators','trading_financials'} <= BASE_TOOLS
    tools = FinancialTools()
    for args in [ARGS | {'url':'http://localhost'}, ARGS | {'symbol':'AAPL,MSFT'}, ARGS | {'api_key':'secret'}]:
        assert json.loads(tools.call('price_history',args)) == {'error':'invalid_financial_arguments'}


def test_timeout_terminates_worker_and_releases_capacity():
    tools = FinancialTools(timeout=.1, command=[sys.executable,'-c','import time; time.sleep(60)'])
    start = time.monotonic()
    assert json.loads(tools.call('price_history',ARGS)) == {'error':'financial_query_timeout'}
    assert time.monotonic()-start < 3
    assert json.loads(tools.call('price_history',ARGS))['error'] == 'financial_query_timeout'


def test_cancel_running_worker_and_oversized_output_are_bounded():
    start = time.monotonic()
    tools = FinancialTools(command=[sys.executable,'-c','import time; time.sleep(60)'],
                           cancelled=lambda:time.monotonic()-start>.15)
    assert json.loads(tools.call('price_history',ARGS))['error'] == 'financial_query_cancelled'
    assert time.monotonic()-start < 3
    tools = FinancialTools(command=[sys.executable,'-c','print("x"*600000)'])
    assert json.loads(tools.call('price_history',ARGS))['error'] == 'financial_response_too_large'


def test_credentials_are_not_inherited_and_provider_error_is_redacted(monkeypatch):
    monkeypatch.setenv('EODHD_API_KEY','very-private')
    command = [sys.executable,'-c','import os,json; print(json.dumps({"error":os.environ.get("EODHD_API_KEY","private-provider-url")}))']
    result = FinancialTools(command=command).call('price_history',ARGS)
    assert json.loads(result) == {'error':'financial_provider_failed'}
    tools = FinancialTools(command=[sys.executable,'-c','import os,json; print(json.dumps({"credential_present":"EODHD_API_KEY" in os.environ}))'])
    assert json.loads(tools.call('price_history',ARGS))['credential_present'] is False


def test_rate_limit_is_not_cached_and_success_is_cached():
    tools = FinancialTools(command=[sys.executable,'-c','print(\'{"error":"rate_limited"}\')'])
    assert json.loads(tools.call('price_history',ARGS))['error'] == 'rate_limited'
    tools.command = [sys.executable,'-c','print(\'{"symbol":"AAPL"}\')']
    assert json.loads(tools.call('price_history',ARGS)) == {'symbol':'AAPL'}
    tools.command = [sys.executable,'-c','raise SystemExit(1)']
    assert json.loads(tools.call('price_history',ARGS)) == {'symbol':'AAPL'}


def test_concurrent_request_is_rejected_while_worker_runs():
    import threading
    running = threading.Event()
    tools = FinancialTools(timeout=.2,command=[sys.executable,'-c','import time; time.sleep(60)'],cancelled=lambda:running.set() or False)
    thread = threading.Thread(target=lambda:tools.call('price_history',ARGS))
    thread.start()
    assert running.wait(2)
    assert json.loads(tools.call('indicators',ARGS))['error'] == 'financial_query_busy'
    thread.join(2)
    assert not thread.is_alive()


def test_registered_handlers_validate_arguments():
    from integrations.hermes.finance import register_finance
    registered = {}
    class Context:
        def register_tool(self, **kwargs):
            registered[kwargs['name']] = kwargs
    register_finance(Context())
    assert len(registered) == 3
    for tool in registered.values():
        assert tool['schema']['parameters']['additionalProperties'] is False
        assert json.loads(tool['handler']({'symbol':'../x','api_key':'secret'}))['error'] == 'invalid_financial_arguments'


def test_date_validation_gives_safe_repair_guidance_without_running_worker():
    tools = FinancialTools(command=[sys.executable, '-c', 'raise SystemExit(99)'])
    result = json.loads(tools.call('price_history', ARGS | {'end': '2099-01-01'}))
    assert result['error'] == 'invalid_financial_arguments'
    assert 'exclusive' in result['hint'] and 'tomorrow UTC' in result['hint']
    assert '2099' not in json.dumps(result)
