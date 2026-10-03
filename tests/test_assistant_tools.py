import httpx
import pytest

from integrations.hermes.core_client import PlatformClient


def test_submission_retries_same_identity_new_call_new_key():
    requests = []
    def handler(request):
        requests.append(request)
        if len(requests) == 1:
            raise httpx.ReadTimeout('response lost')
        return httpx.Response(201, json={'research_id': '62c544b6-8501-49b0-bf91-831985ac4a9d'})
    client = PlatformClient('http://core', 'private-key', transport=httpx.MockTransport(handler))
    first = client.call('submit', {'ticker': 'AAPL', 'horizon_td': 20}, identity=('session', 'turn', 'call1'))
    client.call('submit', {'ticker': 'AAPL', 'horizon_td': 20}, identity=('session', 'turn', 'call2'))
    assert requests[0].headers['Idempotency-Key'] == requests[1].headers['Idempotency-Key']
    assert requests[1].headers['Idempotency-Key'] != requests[2].headers['Idempotency-Key']
    assert requests[0].headers['Authorization'] == 'Bearer private-key'
    assert first['report_url'].endswith('62c544b6-8501-49b0-bf91-831985ac4a9d')
    with pytest.raises(ValueError):
        client.call('submit', {'ticker': 'AAPL', 'horizon_td': 20}, identity=None)


def test_report_ownership_error_and_path_boundary():
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(404, json={'detail': 'report not found'})
    client = PlatformClient('http://core', 'key', transport=httpx.MockTransport(handler))
    assert client.call('report', {'research_id': '62c544b6-8501-49b0-bf91-831985ac4a9d'}) == {'error': 'Core HTTP 404'}
    with pytest.raises(ValueError):
        client.call('report', {'research_id': '../../admin/tenants'})
    assert len(seen) == 1
