"""Bounded read-only EODHD MCP probes. Output contains metadata, never raw data or keys."""
import hashlib
import json
import os
from datetime import date, timedelta
from urllib.request import Request, urlopen


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
    dates = {'start_date': str(today-timedelta(days=7)), 'end_date': str(today)}
    queries = {
        'resolve_ticker': {'query': 'Apple', 'preferred_exchange': 'US', 'asset_type': 'stock'},
        'get_stocks_from_search': {'query': 'AAPL', 'exchange': 'US', 'limit': 1},
        'get_historical_stock_prices': {'ticker': 'AAPL.US', **dates},
        'get_live_price_data': {'ticker': 'AAPL.US'},
        'get_fundamentals_data': {'ticker': 'AAPL.US', 'sections': ['General'], 'include_financials': False},
        'get_company_news': {'ticker': 'AAPL.US', **dates, 'limit': 1},
        'get_upcoming_earnings': {'symbols': 'AAPL.US', 'start_date': str(today),
                                 'end_date': str(today+timedelta(days=7))},
    }
    report = {'date': str(today), 'server': init['serverInfo'], 'discovered_tools': len(catalog),
              'auth': 'Authorization Bearer header', 'checks': {}, 'paid_model_calls': False}
    for name, args in queries.items():
        schema = next(tool['inputSchema'] for tool in catalog if tool['name'] == name)
        result = rpc('tools/call', {'name': name, 'arguments': args})
        payload = result.get('result', {})
        encoded = json.dumps(payload)
        status = 'success'
        if result.get('error') or payload.get('isError'):
            status = 'error'
            if any(word in encoded.lower() for word in ('403', 'subscription', 'access denied', 'not available in your')):
                status = 'subscription_denied'
            elif '429' in encoded:
                status = 'rate_limited'
        report['checks'][name] = {'status': status, 'response_bytes': len(encoded.encode()),
            'schema_sha256': hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()}
    print(json.dumps(report, indent=2))
    assert all(c['status'] == 'success' for c in report['checks'].values()), 'some live capabilities failed; inspect status metadata'


if __name__ == '__main__':
    try:
        verify()
    except Exception as exc:
        # Never print request objects, tracebacks or exception strings containing supplier URLs.
        print(json.dumps({'probe_failure': type(exc).__name__}))
        raise SystemExit(1)
