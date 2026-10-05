"""Trusted finance worker with cancellation, bounded output and memory-only cache."""
from collections import OrderedDict
import json
import os
import selectors
import signal
import subprocess
import sys
import threading
import time
from pydantic import ValidationError
from trading_core import PriceQuery, FinancialQuery


def interrupted():
    try:
        from tools.interrupt import is_interrupted
        return is_interrupted()
    except ImportError:
        return False


class FinancialTools:
    def __init__(self, *, timeout=40, command=None, cancelled=interrupted):
        self.timeout = timeout
        self.command = command or [sys.executable, '-m', 'trading_core']
        self.cancelled = cancelled
        self.lock = threading.Lock()
        self.cache = OrderedDict()

    def call(self, operation, arguments):
        def error(code):
            return json.dumps({'error':code})
        try:
            if operation not in {'price_history','indicators','financials','analysis'}:
                raise ValueError('operation')
            query = (FinancialQuery if operation == 'financials' else PriceQuery)(**arguments)
            request = json.dumps({'operation':operation, 'arguments':query.model_dump(mode='json')},sort_keys=True)
        except ValidationError as exc:
            errors = exc.errors(include_input=False, include_context=False, include_url=False)
            if operation in {'price_history', 'indicators', 'analysis'} and all(
                    tuple(item['loc']) in {(), ('start',), ('end',)} for item in errors):
                return json.dumps({'error': 'invalid_financial_arguments', 'hint':
                    'Use ISO dates: start inclusive, end exclusive, start < end, at most five years. '
                    'End may be at most tomorrow UTC to include today. Current-day data may be incomplete or unavailable.'})
            return error('invalid_financial_arguments')
        except (ValueError, TypeError):
            return error('invalid_financial_arguments')
        if not self.lock.acquire(blocking=False):
            return error('financial_query_busy')
        try:
            if self.cancelled():
                return error('financial_query_cancelled')
            now = time.monotonic()
            for key in list(self.cache):
                if now - self.cache[key][0] >= 120:
                    del self.cache[key]
            if request in self.cache:
                return self.cache[request][1]
            # No platform, LLM or supplier credentials are inherited by this worker.
            env = {k:v for k,v in os.environ.items() if k in ('PATH','LANG','LC_ALL','SYSTEMROOT','TRADING_SEC_USER_AGENT')}
            env.update(PYTHONUNBUFFERED='1',PYTHONDONTWRITEBYTECODE='1')
            process = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.DEVNULL, env=env, start_new_session=True)
            try:
                process.stdin.write(request.encode())
                process.stdin.close()
                output = bytearray()
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout,selectors.EVENT_READ)
                    while True:
                        if self.cancelled():
                            return error('financial_query_cancelled')
                        if time.monotonic() - now >= self.timeout:
                            return error('financial_query_timeout')
                        ready = selector.select(.05)
                        if not ready:
                            continue
                        chunk = os.read(process.stdout.fileno(),65536)
                        if not chunk:
                            break
                        output.extend(chunk)
                        if len(output)>512*1024:
                            return error('financial_response_too_large')
                process.wait(timeout=max(.01,self.timeout-(time.monotonic()-now)))
                if process.returncode:
                    return error('financial_provider_failed')
                result = json.loads(output)
                if not isinstance(result,dict):
                    return error('financial_provider_failed')
                if 'error' in result:
                    # Worker emits controlled codes; never pass arbitrary errors.
                    safe = {'rate_limited','empty_result','sec_symbol_not_found','sec_contact_not_configured',
                            'sec_connection_failed','price_provider_failed','unsupported_market_or_missing_metadata',
                            'sec_http_403','sec_http_404','sec_http_503'}
                    return error(result['error'] if result['error'] in safe else 'financial_provider_failed')
                rendered = json.dumps(result,ensure_ascii=False,allow_nan=False)
                self.cache[request] = (time.monotonic(),rendered)
                while len(self.cache)>16:
                    self.cache.popitem(last=False)
                return rendered
            finally:
                if process.poll() is None:
                    os.killpg(process.pid,signal.SIGKILL)
                process.wait()
                process.stdout.close()
        except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
            return error('financial_provider_failed')
        finally:
            self.lock.release()


_tools = FinancialTools()


def register_finance(ctx):
    for operation, model, description in (
        ('analysis', PriceQuery, 'Preferred stock trend analysis: one Yahoo fetch returns requested-period daily prices, return/drawdown/volatility, and SMA20/50/200 + RSI with up to 400 calendar days of warmup. indicator_history describes the separate warmup window; do not use it as the requested return period. No need to call price_history or indicators again for the same analysis.'),
        ('price_history', PriceQuery, 'Default free US stock/ETF historical daily prices (Yahoo). One symbol, ISO start inclusive/end exclusive, at most five years. Raw vendor OHLC and adjusted close remain separate. Not live or formal PIT.'),
        ('indicators', PriceQuery, 'Default free indicators: fetch validated Yahoo adjusted closes internally, then SMA20/50/200, Wilder RSI14, interval return, annualized sample volatility, max drawdown. One symbol and explicit ISO dates; no price arrays. Missing samples carry reasons.'),
        ('financials', FinancialQuery, 'Default free SEC US-GAAP financials: revenue, net income, assets, liabilities, operating cash flow. Defaults to four explicit quarters; max eight quarters or five years. Cumulative values never substituted. Missing tags/quarters remain missing. Latest filings, not formal PIT.'),
    ):
        name = 'trading_' + operation
        def handler(args, _operation=operation, **kwargs):
            return _tools.call(_operation,args)
        ctx.register_tool(name=name, toolset='youwei-assistant', handler=handler,
                          schema=dict(name=name,description=description,parameters=model.model_json_schema()))
