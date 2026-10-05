"""Native finance acceptance in a disposable HOME, no model calls."""
import argparse
import json
import os
from pathlib import Path
import sys
import time


def verify(live):
    sys.path.insert(0,'/opt/youwei-assistant')
    from bootstrap import install_profile, discovered_tools
    from policy import BASE_TOOLS
    install_profile(Path(os.environ['HERMES_HOME']))
    from model_tools import handle_function_call
    with discovered_tools() as names:
        assert BASE_TOOLS <= names
        # This substitution lives solely in the acceptance script, not runtime config.
        finance = next(module for name,module in list(sys.modules.items()) if name.endswith('.finance') and hasattr(module,'FinancialTools'))
        if not live:
            finance._tools.command=[sys.executable,str(Path(__file__).with_name('finance_fixture_worker.py'))]
        results=[]
        symbols=['AAPL','MSFT','SPY'] if live else ['AAPL']
        for symbol in symbols:
            for tool in ('trading_price_history','trading_indicators'):
                args=dict(symbol=symbol,start='2026-09-01' if live else '2025-01-01',end='2026-10-03' if live else '2025-02-01')
                body=json.loads(handle_function_call(tool,args))
                ok=('error' not in body and body.get('symbol')==symbol and
                    (len(body.get('rows',[]))>=15 if tool.endswith('history') else body.get('metrics',{}).get('sma20',{}).get('value') is not None))
                results.append(dict(tool=tool,symbol=symbol,status='passed' if ok else 'failed',result=body))
        for symbol in (['AAPL','MSFT'] if live else ['AAPL']):
            body=json.loads(handle_function_call('trading_financials',dict(symbol=symbol)))
            periods=body.get('periods',[])
            ok=('error' not in body and len(periods)>0 and any(p['metrics']['revenue']['value'] is not None for p in periods))
            results.append(dict(tool='trading_financials',symbol=symbol,status='passed' if ok else 'failed',result=body))
        if not live:
            for name in ('trading_price_history','trading_indicators','trading_financials'):
                assert json.loads(handle_function_call(name,{'symbol':'../x','api_key':'secret'}))['error']=='invalid_financial_arguments'
            from tools.interrupt import set_interrupt
            set_interrupt(True)
            try:
                assert 'cancelled' in handle_function_call('trading_price_history',dict(symbol='AAPL',start='2025-01-01',end='2025-02-01'))
            finally:
                set_interrupt(False)
        print(json.dumps(dict(mode='live' if live else 'offline',tool_count=len(names),queries=results,passed=all(r['status']=='passed' for r in results)),ensure_ascii=False))
        return all(r['status']=='passed' for r in results)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true')
    raise SystemExit(0 if verify(parser.parse_args().live) else 1)
