"""Offline acceptance worker, never copied into the runtime image."""
import json
import sys
import httpx
import pandas as pd
from trading_core import PriceQuery, FinancialQuery, get_price_history, get_indicators, get_financials, get_analysis


class Yahoo:
    def history(self, **kwargs):
        return pd.DataFrame({key:[100.0]*21 for key in ('Open','High','Low','Close','Adj Close','Volume')},
                            index=pd.date_range('2025-01-02',periods=21,freq='B',tz='America/New_York'))
    def get_history_metadata(self):
        return dict(currency='USD',exchangeTimezoneName='America/New_York',instrumentType='EQUITY',exchangeName='NMS')


def sec(request):
    if request.url.host=='www.sec.gov':
        body={'0':dict(ticker='AAPL',cik_str=320193)}
    elif '/submissions/' in request.url.path:
        body=dict(cik=320193,filings=dict(recent=dict(form=['10-Q'],reportDate=['2025-12-27'])))
    else:
        row=dict(start='2025-09-28',end='2025-12-27',val=100,filed='2026-01-30',accn='0000320193-26-000001',form='10-Q')
        body=dict(cik=320193,facts={'us-gaap':{'Revenues':{'units':{'USD':[row]}}}})
    return httpx.Response(200,json=body)


request=json.load(sys.stdin)
operation,args=request['operation'],request['arguments']
if operation=='financials':
    result=get_financials(FinancialQuery(**args),user_agent='fixture test@example.com',transport=httpx.MockTransport(sec))
else:
    result={'price_history':get_price_history,'indicators':get_indicators,'analysis':get_analysis}[operation](PriceQuery(**args),ticker_factory=lambda symbol:Yahoo())
print(json.dumps(result))
