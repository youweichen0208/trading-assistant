"""The single source of the personal assistant tool allowlist."""
BASE_TOOLS = frozenset({'web_search', 'web_extract', 'memory', 'youwei_platform', 'youwei_knowledge'})
EODHD_TOOLS = frozenset({
    'resolve_ticker', 'get_stocks_from_search', 'get_historical_stock_prices',
    'get_live_price_data', 'get_company_news', 'get_intraday_historical_data',
    'get_us_live_extended_quotes', 'get_historical_dividends', 'get_historical_splits',
    'get_sentiment_data', 'get_news_word_weights', 'get_technical_indicators',
    'stock_screener', 'get_historical_commodity_prices', 'get_ust_bill_rates',
    'get_ust_yield_rates', 'get_ust_real_yield_rates', 'get_ust_long_term_rates',
    'capture_realtime_ws',
})
MCP_TOOLS = frozenset('mcp__eodhd__' + name for name in EODHD_TOOLS)


def validate_tools(names):
    names = set(names)
    if not BASE_TOOLS <= names or not names <= BASE_TOOLS | MCP_TOOLS:
        raise ValueError('assistant tool allowlist did not load safely')
