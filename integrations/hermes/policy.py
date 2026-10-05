"""The single source of the personal assistant tool allowlist."""
BASE_TOOLS = frozenset({'web_search', 'web_extract', 'memory', 'youwei_platform', 'youwei_knowledge',
                       'trading_price_history', 'trading_indicators', 'trading_financials'})
# Release scope: deployed seven-tool baseline plus the two purchased Marketplace tools.
# The extended-plan experiment remains archived at d9f69c5; it is not enabled here.
EODHD_TOOLS = frozenset({
    'resolve_ticker', 'get_stocks_from_search', 'get_historical_stock_prices',
    'get_live_price_data', 'get_fundamentals_data', 'get_company_news',
    'get_upcoming_earnings', 'mp_indices_list', 'mp_index_components',
})
MCP_TOOLS = frozenset('mcp__eodhd__' + name for name in EODHD_TOOLS)


def validate_tools(names):
    names = set(names)
    if not BASE_TOOLS <= names or not names <= BASE_TOOLS | MCP_TOOLS:
        raise ValueError('assistant tool allowlist did not load safely')
