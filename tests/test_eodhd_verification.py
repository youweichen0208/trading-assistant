import json

from ops.verify_eodhd_live import inspect_result


def envelope(value):
    return {'result': {'isError': False, 'structuredContent': {'result': json.dumps(value)}}}


def test_nested_supplier_denial_is_not_success():
    assert inspect_result('get_technical_indicators', {}, envelope({'error': 'Forbidden', 'status_code': 403}))['status'] == 'subscription_denied'


def test_quote_requires_symbol_price_and_timestamp():
    args = {'ticker': 'AAPL.US'}
    assert inspect_result('get_live_price_data', args, envelope({'code': 'MSFT.US', 'close': 1, 'timestamp': 1}))['status'] == 'invalid_response'
    assert inspect_result('get_live_price_data', args, envelope({'code': 'AAPL.US', 'close': 1, 'timestamp': 1}))['status'] == 'success'


def test_empty_and_transport_error_are_distinct():
    assert inspect_result('get_historical_splits', {}, envelope([]))['status'] == 'empty'
    result = {'result': {'isError': True, 'content': [{'type': 'text', 'text': 'no close frame received or sent'}]}}
    assert inspect_result('capture_realtime_ws', {}, result)['status'] == 'connection_failed'


def test_dates_outside_requested_range_are_reported():
    result = envelope({'AAPL.US': [{'date': '2026-09-27', 'count': 1, 'normalized': 0.5}]})
    args = {'symbols': 'AAPL.US', 'start_date': '2026-09-28', 'end_date': '2026-10-05'}
    assert inspect_result('get_sentiment_data', args, result)['status'] == 'invalid_response'
