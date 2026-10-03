"""Fixed Core HTTP operations; tenant identity never comes from model arguments."""
import hashlib
import json
from uuid import UUID

import httpx


class PlatformClient:
    def __init__(self, base_url, api_key, *, dashboard_url='https://dash.youwei-agent.com', transport=None):
        self.base_url, self.api_key = base_url.rstrip('/'), api_key
        self.dashboard_url, self.transport = dashboard_url.rstrip('/'), transport

    def call(self, action, arguments, *, identity=None):
        args = dict(arguments)
        method, path, body, params = 'GET', '/v1/research', None, None
        headers = {'Authorization': 'Bearer ' + self.api_key}
        if action == 'daily_bars':
            if not {'ticker', 'start_date', 'end_date'} <= args.keys() or args.keys() - {'ticker', 'start_date', 'end_date', 'as_of'}:
                raise ValueError('daily_bars requires ticker, start_date, end_date; optional as_of')
            path, params = '/v1/data/daily-bars', args
        elif action == 'submit':
            if not identity or len(identity) != 3 or not all(identity):
                raise ValueError('submission requires runtime session, turn and tool-call identity')
            if not {'ticker', 'horizon_td'} <= args.keys() or args.keys() - {'ticker', 'horizon_td', 'benchmark_ticker'}:
                raise ValueError('submit accepts ticker, horizon_td and optional benchmark_ticker only')
            if args['horizon_td'] not in (1, 20, 60):
                raise ValueError('horizon_td must be 1, 20 or 60')
            method, body = 'POST', args
            headers['Idempotency-Key'] = 'hermes:' + hashlib.sha256(json.dumps(identity).encode()).hexdigest()
        elif action == 'list':
            if args.keys() - {'limit'}:
                raise ValueError('list accepts only limit')
            params = args
        elif action in ('status', 'report', 'cancel'):
            research_id = str(UUID(args.pop('research_id')))
            if args.keys() - ({'version'} if action == 'report' else set()):
                raise ValueError('unexpected arguments')
            path += '/' + research_id
            if action == 'report':
                path += '/report'; params = args
            elif action == 'cancel':
                method, path = 'POST', path + '/cancel'
        else:
            raise ValueError('unknown platform operation')
        with httpx.Client(base_url=self.base_url, headers=headers, transport=self.transport,
                          timeout=30, follow_redirects=False, trust_env=False) as client:
            for attempt in range(2):
                try:
                    response = client.request(method, path, json=body, params=params)
                    break
                except httpx.TransportError:
                    if attempt:
                        return {'error': 'Core transport failure; submission status unknown. Retry the same tool call, do not create a new request.'}
            if response.status_code >= 300:
                return {'error': f'Core HTTP {response.status_code}'}
            result = response.json()
        if action in ('submit', 'status') and isinstance(result, dict) and result.get('research_id'):
            result['report_url'] = self.dashboard_url + '/#/research/' + str(UUID(result['research_id']))
        return result
