"""The single source of the personal assistant tool allowlist."""
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


