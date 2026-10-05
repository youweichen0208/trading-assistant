"""Personal stock-query policy around Hermes' unmodified native MCP client."""
import json
import logging
import os
import re
import traceback
from datetime import date, datetime, timezone
from urllib.parse import quote, quote_plus


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
    if tool in {'mp_indices_list', 'mp_index_components'}:
        if args.get('fmt', 'json') != 'json':
            return json.dumps({'error': 'Marketplace index queries require JSON format'})
        if tool == 'mp_index_components':
            symbol = args.get('symbol')
            if not isinstance(symbol, str) or not re.fullmatch(r'[A-Z0-9][A-Z0-9_-]{0,63}\.INDX', symbol):
                return json.dumps({'error': 'provide one index symbol from mp_indices_list, e.g. GSPC.INDX'})
    if tool == 'get_fundamentals_data' and not args.get('sections'):
        args['sections'] = ['General', 'Highlights', 'Valuation']
        args['include_financials'] = False
    try:
        dated = {'get_historical_stock_prices', 'get_historical_dividends',
                 'get_historical_splits', 'get_technical_indicators',
                 'get_sentiment_data', 'get_news_word_weights'}
        if tool in dated or (tool == 'get_company_news' and
                             any(k in args for k in ('start_date', 'end_date'))):
            start, end = (date.fromisoformat(args[k]) for k in ('start_date', 'end_date'))
            if end < start:
                raise ValueError('dates must be in order')
        if tool == 'get_intraday_historical_data':
            def timestamp(value):
                if type(value) is int:
                    return datetime.fromtimestamp(value, timezone.utc)
                parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
                return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
            if timestamp(args['to_timestamp']) < timestamp(args['from_timestamp']):
                raise ValueError('timestamps must be in order')
        if tool.startswith('get_ust_'):
            year = args['year']
            if type(year) is not int or not 1900 <= year <= date.today().year + 1:
                raise ValueError('explicit integer year required')
        limits = {}
        if tool in {'get_company_news', 'stock_screener', 'get_news_word_weights'}:
            limits['limit'] = (10, 50, int)
        if tool == 'capture_realtime_ws':
            limits = {'duration_seconds': (5, 10, int), 'max_messages': (100, 100, int),
                      'max_data_bytes': (1048576, 1048576, int),
                      'connect_timeout': (5, 5, (int, float))}
        for field, (default, maximum, types) in limits.items():
            value = args.setdefault(field, default)
            if isinstance(value, bool) or not isinstance(value, types) or not 0 < value <= maximum:
                raise ValueError(field + ' exceeds query policy or has invalid type')
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError):
        return json.dumps({'error': 'EODHD query requires explicit ordered dates/year and bounded numeric limits'})
    try:
        return redact(next_call(args))
    except Exception as exc:
        # Transport errors can carry a supplier URL containing its token.
        return json.dumps({'error': 'EODHD query failed', 'kind': type(exc).__name__,
                           'detail': redact(str(exc))})
