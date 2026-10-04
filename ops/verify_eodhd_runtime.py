"""Run inside the candidate/running image: native discovery and one read-only quote, no LLM."""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, '/opt/youwei-assistant')
from eodhd import BASE_TOOLS, MCP_TOOLS, install_secret_redaction, validate_tools


def verify():
    install_secret_redaction()
    assert os.environ.get('EODHD_API_KEY'), 'EODHD credential missing'
    home = Path(os.environ['HERMES_HOME'])
    # New disposable containers initialize a profile; live checks only read it.
    if not (home/'config.yaml').exists():
        home.mkdir(parents=True, exist_ok=True)
        (home/'plugins').mkdir(exist_ok=True)
        (home/'plugins/youwei-assistant').symlink_to('/opt/youwei-assistant')
        (home/'config.yaml').write_bytes(Path('/opt/youwei-assistant/config.yaml').read_bytes())
    from hermes_cli.plugins import discover_plugins
    from hermes_cli.config import load_config
    from hermes_cli.tools_config import _get_platform_tools
    from tools.mcp_tool_discovery import discover_mcp_tools
    from tools.mcp_tool_lifecycle import shutdown_mcp_servers
    from model_tools import get_tool_definitions, handle_function_call
    discover_plugins()
    try:
        discover_mcp_tools(allowed_mcp_names=['eodhd'])
        names = {t['function']['name'] for t in get_tool_definitions(
            enabled_toolsets=sorted(_get_platform_tools(load_config(), 'api_server')), quiet_mode=True)}
        validate_tools(names)
        assert names == BASE_TOOLS | MCP_TOOLS, 'seven MCP tools must be discoverable at release acceptance'
        result = handle_function_call('mcp__eodhd__get_live_price_data', {'ticker': 'AAPL.US'},
                                      enabled_tools=sorted(names))
        assert 'AAPL' in result and 'price' in result and '"error"' not in result, 'native quote failed'
        assert os.environ['EODHD_API_KEY'] not in result, 'credential leaked'
        print(json.dumps({'result': 'PASS', 'tool_names': sorted(names), 'native_quote': True,
                          'paid_model_calls': False}))
    finally:
        shutdown_mcp_servers()


if __name__ == '__main__':
    try:
        verify()
    except Exception as exc:
        print(json.dumps({'result': 'FAIL', 'kind': type(exc).__name__}))
        raise SystemExit(1)
