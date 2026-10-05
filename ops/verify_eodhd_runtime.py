"""Run inside the candidate/running image: native discovery, quote and purchased index data, no LLM."""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, '/opt/youwei-assistant')
from policy import BASE_TOOLS, MCP_TOOLS
from eodhd import install_secret_redaction
from bootstrap import install_profile, discovered_tools
from verify_eodhd_live import inspect_result


def verify():
    install_secret_redaction()
    assert os.environ.get('EODHD_API_KEY'), 'EODHD credential missing'
    home = Path(os.environ['HERMES_HOME'])
    # New disposable containers initialize a profile; live checks only read it.
    if not (home/'config.yaml').exists():
        install_profile(home)
    from model_tools import handle_function_call
    with discovered_tools() as names:
        assert names == BASE_TOOLS | MCP_TOOLS, 'all configured MCP tools must be discoverable at release acceptance'
        result = handle_function_call('mcp__eodhd__get_live_price_data', {'ticker': 'AAPL.US'},
                                      enabled_tools=sorted(names))
        payload = json.loads(result)
        assert 'error' not in payload, 'native quote failed'
        quote = payload.get('result')
        if isinstance(quote, str):
            quote = json.loads(quote)
        assert isinstance(quote, dict) and quote.get('code') == 'AAPL.US', 'unexpected quote symbol'
        assert isinstance(quote.get('close'), (int, float)) and quote.get('timestamp'), 'quote fields missing'
        assert os.environ['EODHD_API_KEY'] not in result, 'credential leaked'
        marketplace = {}
        for tool, args in [('mp_indices_list', {}), ('mp_index_components', {'symbol': 'GSPC.INDX'})]:
            raw = handle_function_call('mcp__eodhd__' + tool, args, enabled_tools=sorted(names))
            assert os.environ['EODHD_API_KEY'] not in raw, 'credential leaked'
            payload = json.loads(raw)
            assert 'error' not in payload, 'native Marketplace call failed'
            check = inspect_result(tool, args, {'result': {'structuredContent': payload}})
            assert check['status'] == 'success', 'Marketplace structure validation failed: ' + tool
            marketplace[tool] = check
        print(json.dumps({'result': 'PASS', 'marketplace': marketplace, 'tool_names': sorted(names), 'native_quote': True,
                          'paid_model_calls': False}))


if __name__ == '__main__':
    try:
        verify()
    except Exception as exc:
        print(json.dumps({'result': 'FAIL', 'kind': type(exc).__name__,
                          'check': str(exc) if isinstance(exc, AssertionError) else 'runtime exception'}))
        raise SystemExit(1)
