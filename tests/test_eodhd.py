import json
import logging

import pytest

from integrations.hermes import tool_boundary
from integrations.hermes.eodhd import BASE_TOOLS, MCP_TOOLS, validate_tools, install_secret_redaction


def invoke(name, args, handler=lambda args: json.dumps(args)):
    return tool_boundary(tool_name=name, args=args, next_call=handler)


def test_stock_tools_and_unknown_tools():
    for name in MCP_TOOLS:
        args = {'ticker': 'AAPL.US', 'start_date': '2026-10-01', 'end_date': '2026-10-02'}
        assert json.loads(invoke(name, args))['ticker'] == 'AAPL.US'
    assert 'error' in json.loads(invoke('mcp__eodhd__get_user_details', {}))
    assert 'error' in json.loads(invoke('mcp__other__get_live_price_data', {}))


@pytest.mark.parametrize('args', [{'api_token': 'override'}, {'api_key': 'override'},
                                  {'extra_params': {'api_token': 'override'}}])
def test_credentials_cannot_be_overridden(args):
    def forbidden(_):
        pytest.fail('must reject before dispatch')
    assert 'error' in json.loads(invoke('mcp__eodhd__get_fundamentals_data', args, forbidden))


def test_bounded_queries():
    name = 'mcp__eodhd__get_historical_stock_prices'
    assert 'error' in json.loads(invoke(name, {'ticker': 'AAPL.US'}))
    assert json.loads(invoke('mcp__eodhd__get_company_news', {'ticker': 'AAPL.US'}))['limit'] == 10


def test_startup_allows_outage_but_not_boundary_drift():
    validate_tools(BASE_TOOLS)
    validate_tools(BASE_TOOLS | MCP_TOOLS)
    with pytest.raises(ValueError):
        validate_tools(BASE_TOOLS - {'memory'})
    with pytest.raises(ValueError):
        validate_tools(BASE_TOOLS | {'terminal'})


def test_results_and_exceptions_are_redacted(monkeypatch):
    secret = 'test-private-eodhd-token'
    monkeypatch.setenv('EODHD_API_KEY', secret)
    name = 'mcp__eodhd__get_live_price_data'
    assert secret not in invoke(name, {}, lambda _: json.dumps({'error': 'url?api_token='+secret}))
    def failed(_):
        raise TimeoutError('request '+secret)
    result = json.loads(invoke(name, {}, failed))
    assert 'error' in result and secret not in json.dumps(result)


def test_log_redaction(monkeypatch):
    secret = 'test-private-eodhd-token'
    monkeypatch.setenv('EODHD_API_KEY', secret)
    old_factory = logging.getLogRecordFactory()
    try:
        install_secret_redaction()
        record = logging.getLogRecordFactory()('mcp', logging.ERROR, __file__, 1, 'URL %s', (secret,), None)
        assert secret not in record.getMessage()
    finally:
        logging.setLogRecordFactory(old_factory)
