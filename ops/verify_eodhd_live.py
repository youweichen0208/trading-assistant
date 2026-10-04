"""Bounded read-only EODHD MCP probes. Output contains metadata, never raw data or keys."""
import hashlib
import json
import os
from datetime import date, timedelta, datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def inspect_result(name, args, result):
    """Validate decoded supplier data, including errors hidden inside successful MCP envelopes."""
    payload = result.get('result', {})
    value = payload.get('structuredContent', {}).get('result')
    if value is None:
        texts = [c['text'] for c in payload.get('content', []) if c.get('type') == 'text']
        value = texts[0] if len(texts) == 1 else texts
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            pass
    error = result.get('error') or payload.get('isError') or (isinstance(value, dict) and value.get('error'))
    if error:
        text = json.dumps(result).lower()
        status = 'supplier_error'
        if any(w in text for w in ('403', 'subscription', 'access denied')):
            status = 'subscription_denied'
        elif any(w in text for w in ('429', '402', 'quota', 'rate limit')):
            status = 'rate_limited'
        elif any(w in text for w in ('close frame', 'connection', 'timeout', 'timed out')):
            status = 'connection_failed'
        elif any(w in text for w in ('invalid param', 'validation', '422', '-32602')):
            status = 'parameter_error'
        return {'status': status}
    try:
        rows = value
        checks = []
        if name == 'resolve_ticker':
            assert value['resolved'] == 'AAPL.US' and value['exchange'] == 'US'
            checks.append('resolved_symbol_exchange')
        elif name == 'get_stocks_from_search':
            assert value and value[0]['Code'] == 'AAPL' and value[0]['Exchange'] == 'US'
            checks.append('search_symbol_exchange')
        elif name == 'get_live_price_data':
            assert value['code'] == args['ticker'] and isinstance(value['close'], (int, float)) and value['timestamp']
            checks.append('quote_symbol_price_timestamp')
        elif name == 'get_us_live_extended_quotes':
            quote = value['data']['AAPL.US']
            assert quote['symbol'] == 'AAPL.US' and isinstance(quote['lastTradePrice'], (int, float)) and quote['timestamp']
            checks.append('extended_symbol_price_timestamp')
        elif name == 'get_news_word_weights':
            rows = value['data']
            assert isinstance(rows, dict) and all(isinstance(v, (int, float)) for v in rows.values())
            checks.append('word_numeric_weights')
        elif name == 'capture_realtime_ws':
            # An error or an empty collection is never acceptance of a live feed.
            assert isinstance(value, dict) and isinstance(value.get('messages'), list) and value['messages']
            assert all(isinstance(row, dict) for row in value['messages'])
            checks.append('received_messages')
        else:
            fields = {
                'get_historical_stock_prices': ('date', 'close'),
                'get_intraday_historical_data': ('datetime', 'close'),
                'get_historical_dividends': ('date', 'value'),
                'get_historical_splits': ('date', 'split'),
                'get_company_news': ('date', 'title', 'link'),
                'get_sentiment_data': ('date', 'count', 'normalized'),
                'get_technical_indicators': ('date', args.get('function', 'sma')),
                'stock_screener': ('code', 'exchange'),
                'get_historical_commodity_prices': ('date', 'value'),
                'get_ust_bill_rates': ('date', 'tenor', 'discount', 'coupon'),
                'get_ust_yield_rates': ('date', 'tenor', 'rate'),
                'get_ust_real_yield_rates': ('date', 'tenor', 'rate'),
                'get_ust_long_term_rates': ('date', 'rate_type', 'rate'),
            }[name]
            if name == 'get_sentiment_data':
                rows = value[args['symbols']]
            elif isinstance(value, dict):
                rows = value['data']
            assert isinstance(rows, list)
            for row in rows:
                assert isinstance(row, dict) and all(field in row for field in fields)
                if 'date' in row:
                    day = date.fromisoformat(row['date'][:10])
                    if 'start_date' in args:
                        assert date.fromisoformat(args['start_date']) <= day <= date.fromisoformat(args['end_date'])
                    if 'year' in args:
                        assert day.year == args['year']
            checks.append('required_fields_and_dates')
        count = len(rows) if isinstance(rows, list) else None
        if rows == [] or rows == {}:
            return {'status': 'empty', 'validated': checks, 'rows': 0}
        report = {'status': 'success', 'validated': checks, 'rows': count}
        if count is not None and 'limit' in args and count > args['limit']:
            report['limit_ignored'] = True
        return report
    except (AssertionError, KeyError, TypeError, ValueError, IndexError):
        return {'status': 'invalid_response', 'reason': 'required symbol, fields or date bounds not satisfied'}


def probe_queries(today):
    dates = {'start_date': str(today-timedelta(days=7)), 'end_date': str(today)}
    queries = {
        'resolve_ticker': {'query': 'Apple', 'preferred_exchange': 'US', 'asset_type': 'stock'},
        'get_stocks_from_search': {'query': 'AAPL', 'exchange': 'US', 'limit': 1},
        'get_historical_stock_prices': {'ticker': 'AAPL.US', **dates},
        'get_live_price_data': {'ticker': 'AAPL.US'},
        'get_company_news': {'ticker': 'AAPL.US', **dates, 'limit': 1},
        'get_intraday_historical_data': {'ticker': 'AAPL.US', 'interval': '5m',
                                        'from_timestamp': '2026-10-02T13:30:00Z', 'to_timestamp': '2026-10-02T14:00:00Z'},
        'get_us_live_extended_quotes': {'symbols': ['AAPL.US'], 'page_limit': 1},
        'get_historical_dividends': {'ticker': 'AAPL.US', 'start_date': '2026-01-01', 'end_date': str(today)},
        'get_historical_splits': {'ticker': 'AAPL.US', 'start_date': '2020-08-01', 'end_date': '2020-09-01'},
        'get_sentiment_data': {'symbols': 'AAPL.US', **dates},
        'get_news_word_weights': {'ticker': 'AAPL.US', **dates, 'limit': 10},
        'get_technical_indicators': {'ticker': 'AAPL.US', 'function': 'sma', 'period': 10, **dates},
        'stock_screener': {'filters': [['code', '=', 'AAPL']], 'limit': 1},
        'get_historical_commodity_prices': {'code': 'WTI', 'interval': 'annual'},
        **{name: {'year': today.year, 'limit': 1} for name in
           ('get_ust_bill_rates', 'get_ust_yield_rates', 'get_ust_real_yield_rates', 'get_ust_long_term_rates')},
        'capture_realtime_ws': {'feed': 'crypto', 'symbols': ['BTC-USD'], 'duration_seconds': 5,
                                'max_messages': 100, 'max_data_bytes': 1048576, 'connect_timeout': 5},
    }

    return queries


def verify():
    key = os.environ['EODHD_API_KEY']
    headers = {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json',
               'Accept': 'application/json, text/event-stream'}
    counter = 0
    def rpc(method, params, notification=False):
        nonlocal counter
        counter += 1
        body = {'jsonrpc': '2.0', 'method': method, 'params': params}
        if not notification:
            body['id'] = counter
        req = Request('https://mcp.eodhd.com/v1/mcp', json.dumps(body).encode(), headers)
        with urlopen(req, timeout=35) as response:
            if response.headers.get('Mcp-Session-Id'):
                headers['Mcp-Session-Id'] = response.headers['Mcp-Session-Id']
            raw = response.read().decode()
        if not raw:
            return {}
        if raw.startswith(('event:', 'data:')):
            return [json.loads(line[5:].strip()) for line in raw.splitlines() if line.startswith('data:')][-1]
        return json.loads(raw)
    init = rpc('initialize', {'protocolVersion': '2025-03-26', 'capabilities': {},
               'clientInfo': {'name': 'youwei-stock-verification', 'version': '1'}})['result']
    headers['MCP-Protocol-Version'] = init['protocolVersion']
    rpc('notifications/initialized', {}, True)
    catalog = rpc('tools/list', {})['result']['tools']
    today = date.today()
    queries = probe_queries(today)
    report = {'date': str(today), 'queried_at': datetime.now(timezone.utc).isoformat(), 'server': init['serverInfo'], 'discovered_tools': len(catalog),
              'auth': 'Authorization Bearer header', 'checks': {}, 'paid_model_calls': False}
    for name, args in queries.items():
        schema = next(tool['inputSchema'] for tool in catalog if tool['name'] == name)
        try:
            result = rpc('tools/call', {'name': name, 'arguments': args})
            check = inspect_result(name, args, result)
            check['response_bytes'] = len(json.dumps(result).encode())
        except HTTPError as exc:
            check = {'status': {403: 'subscription_denied', 429: 'rate_limited', 402: 'rate_limited',
                                400: 'parameter_error', 422: 'parameter_error'}.get(exc.code, 'connection_failed'),
                     'http_status': exc.code}
        except (URLError, TimeoutError, OSError):
            check = {'status': 'connection_failed'}
        check['arguments'] = args
        check['schema_sha256'] = hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()
        report['checks'][name] = check

    print(json.dumps(report, indent=2))
    assert all(c['status'] in {'success', 'empty'} for c in report['checks'].values()), 'some live capabilities failed; inspect status metadata'


if __name__ == '__main__':
    try:
        verify()
    except Exception as exc:
        # Never print request objects, tracebacks or exception strings containing supplier URLs.
        print(json.dumps({'probe_failure': type(exc).__name__}))
        raise SystemExit(1)
