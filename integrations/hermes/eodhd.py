"""Personal stock-query policy around Hermes' unmodified native MCP client."""
import json
import logging
import os
import traceback
from datetime import date
from urllib.parse import quote, quote_plus

BASE_TOOLS = frozenset({'web_search', 'web_extract', 'memory', 'youwei_platform', 'youwei_knowledge'})
EODHD_TOOLS = frozenset({
    'resolve_ticker', 'get_stocks_from_search', 'get_historical_stock_prices',
    'get_live_price_data', 'get_fundamentals_data', 'get_company_news', 'get_upcoming_earnings',
})
MCP_TOOLS = frozenset('mcp__eodhd__' + name for name in EODHD_TOOLS)


def validate_tools(names):
    names = set(names)
    if not BASE_TOOLS <= names or not names <= BASE_TOOLS | MCP_TOOLS:
        raise ValueError('assistant tool allowlist did not load safely')


def redact(value):
    if isinstance(value, str):
        secret = os.environ.get('EODHD_API_KEY', '')
        if secret:
            for variant in {secret, quote(secret, safe=''), quote_plus(secret)}:
                value = value.replace(variant, '[REDACTED]')
        return value
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def install_secret_redaction():
    previous = logging.getLogRecordFactory()
    if getattr(previous, '_youwei_eodhd_redaction', False):
        return
    def factory(*args, **kwargs):
        record = previous(*args, **kwargs)
        record.msg, record.args = redact(record.getMessage()), ()
        if record.exc_info:
            record.exc_text = redact(''.join(traceback.format_exception(*record.exc_info)))
            record.exc_info = None
        if record.stack_info:
            record.stack_info = redact(record.stack_info)
        return record
    factory._youwei_eodhd_redaction = True
    logging.setLogRecordFactory(factory)


def _has_credentials(value):
    if isinstance(value, dict):
        return any(k.lower() in {'api_key', 'api_token', 'apikey', 'authorization'} and v is not None
                   or _has_credentials(v) for k, v in value.items())
    return isinstance(value, list) and any(_has_credentials(v) for v in value)


def execute_query(name, args, next_call):
    if not isinstance(args, dict) or _has_credentials(args):
        return json.dumps({'error': 'EODHD credentials are server-managed; token overrides are not allowed'})
    args = dict(args)
    tool = name.removeprefix('mcp__eodhd__')
    if tool == 'get_historical_stock_prices':
        try:
            start, end = (date.fromisoformat(args[k]) for k in ('start_date', 'end_date'))
            if end < start:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            return json.dumps({'error': 'historical prices require explicit start_date/end_date (YYYY-MM-DD), in order'})
    if tool == 'get_company_news':
        args.setdefault('limit', 10)
    if tool == 'get_fundamentals_data' and not args.get('sections'):
        args['sections'] = ['General', 'Highlights', 'Valuation']
        args['include_financials'] = False
    try:
        return redact(next_call(args))
    except Exception as exc:
        # Transport errors can carry a supplier URL containing its token.
        return json.dumps({'error': 'EODHD query failed', 'kind': type(exc).__name__,
                           'detail': redact(str(exc))})
