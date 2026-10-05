import json
import logging

import pytest

from integrations.hermes import tool_boundary
from integrations.hermes.policy import BASE_TOOLS, MCP_TOOLS, validate_tools
from integrations.hermes.eodhd import install_secret_redaction, execute_query


def invoke(name, args, handler=lambda args: json.dumps(args)):
    return tool_boundary(tool_name=name, args=args, next_call=handler)


def test_stock_tools_and_unknown_tools():
    for name in MCP_TOOLS:
        args = {'symbol': 'GSPC.INDX', 'ticker': 'AAPL.US', 'start_date': '2026-10-01', 'end_date': '2026-10-02', 'from_timestamp': 1790861400, 'to_timestamp': 1790865000, 'year': 2026}
        assert json.loads(invoke(name, args))['ticker'] == 'AAPL.US'
    assert 'error' in json.loads(invoke('mcp__eodhd__get_user_details', {}))
    assert 'error' in json.loads(invoke('mcp__other__get_live_price_data', {}))


@pytest.mark.parametrize('args', [{'api_token': 'override'}, {'api_key': 'override'},
                                  {'extra_params': {'api_token': 'override'}}])
def test_credentials_cannot_be_overridden(args):
    def forbidden(_):
        pytest.fail('must reject before dispatch')
    assert 'error' in json.loads(invoke('mcp__eodhd__get_live_price_data', args, forbidden))


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


def test_unreleased_extended_tools_are_rejected():
    for tool in ('get_intraday_historical_data', 'capture_realtime_ws', 'stock_screener',
                 'get_ust_bill_rates', 'get_us_live_extended_quotes'):
        assert 'error' in json.loads(invoke('mcp__eodhd__' + tool, {}))


@pytest.mark.parametrize('tool,args', [
    ('get_company_news', {'limit': 51}), ('stock_screener', {'limit': True}),
    ('stock_screener', {'limit': None}), ('stock_screener', {'limit': 0}),
    ('get_historical_dividends', {}), ('get_historical_splits', {}),
    ('get_technical_indicators', {}), ('get_sentiment_data', {}),
    ('get_news_word_weights', {}), ('get_intraday_historical_data', {}),
    ('get_intraday_historical_data', {'from_timestamp': 2, 'to_timestamp': 1}),
    ('get_ust_bill_rates', {}),
    ('capture_realtime_ws', {'duration_seconds': 11}),
    ('capture_realtime_ws', {'max_messages': 101}),
    ('capture_realtime_ws', {'max_data_bytes': 1048577}),
    ('capture_realtime_ws', {'connect_timeout': 6}),
    ('capture_realtime_ws', {'connect_timeout': float('nan')}),
    ('capture_realtime_ws', {'max_messages': None}),
    ('get_live_price_data', {'headers': {'Authorization': 'override'}}),
])
def test_reject_unbounded_queries_before_dispatch(tool, args):
    def forbidden(_):
        pytest.fail('invalid queries must not reach supplier')
    assert 'error' in json.loads(execute_query('mcp__eodhd__' + tool, args, forbidden))


def test_capture_limits_and_metadata_preserved():
    expected = {'duration_seconds': 5, 'max_messages': 100, 'max_data_bytes': 1048576, 'connect_timeout': 5}
    assert json.loads(execute_query('mcp__eodhd__capture_realtime_ws', {}, lambda args: json.dumps(args))) == expected
    payload = {'messages': [], 'truncated': True, 'started_at': '2026-10-05T00:00:00Z', 'duration_seconds': 5}
    assert json.loads(execute_query('mcp__eodhd__capture_realtime_ws', {}, lambda _: json.dumps(payload))) == payload
    assert json.loads(execute_query('mcp__eodhd__stock_screener', {}, lambda args: json.dumps(args)))['limit'] == 10


def test_marketplace_tools_and_release_scope():
    assert json.loads(invoke('mcp__eodhd__mp_indices_list', {})) == {}
    assert json.loads(invoke('mcp__eodhd__mp_index_components', {'symbol': 'GSPC.INDX'}))['symbol'] == 'GSPC.INDX'
    assert MCP_TOOLS == {'mcp__eodhd__' + name for name in (
        'resolve_ticker', 'get_stocks_from_search', 'get_historical_stock_prices',
        'get_live_price_data', 'get_fundamentals_data', 'get_company_news',
        'get_upcoming_earnings', 'mp_indices_list', 'mp_index_components')}


@pytest.mark.parametrize('args', [{}, {'symbol': '../user'}, {'symbol': 'AAPL.US'},
    {'symbol': 'GSPC.INDX,DJI.INDX'}, {'symbol': 'GSPC.INDX', 'api_token': 'override'},
    {'symbol': 'GSPC.INDX', 'fmt': 'csv'}])
def test_marketplace_rejects_invalid_symbols_and_credentials(args):
    def forbidden(_):
        pytest.fail('must reject before dispatch')
    assert 'error' in json.loads(invoke('mcp__eodhd__mp_index_components', args, forbidden))


def test_marketplace_preserves_current_and_historical_sections(monkeypatch):
    monkeypatch.setenv('EODHD_API_KEY', 'synthetic-private-key')
    payload = {'General': {'Code': 'GSPC'}, 'Components': {'0': {'Code': 'AAPL'}},
               'HistoricalTickerComponents': {'0': {'Code': 'OLD', 'StartDate': '2020-01-01',
                   'EndDate': '2021-01-01', 'IsDelisted': 1}}, 'note': 'synthetic-private-key'}
    result = json.loads(invoke('mcp__eodhd__mp_index_components', {'symbol': 'GSPC.INDX'}, lambda _: json.dumps(payload)))
    assert result['HistoricalTickerComponents'] == payload['HistoricalTickerComponents']
    assert result['Components'] == payload['Components']
    assert result['note'] == '[REDACTED]'


def test_deployed_fundamentals_default_is_preserved():
    result = json.loads(invoke('mcp__eodhd__get_fundamentals_data', {'ticker': 'AAPL.US'}))
    assert result['sections'] == ['General', 'Highlights', 'Valuation']
    assert result['include_financials'] is False
