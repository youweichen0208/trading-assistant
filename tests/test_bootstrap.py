"""One policy drives generated configuration and native tool enforcement."""
import pytest
from integrations.hermes.bootstrap import configure_tools
from integrations.hermes.policy import EODHD_TOOLS, BASE_TOOLS, MCP_TOOLS, validate_tools


@pytest.mark.parametrize('enabled', [False, True])
def test_profile_applies_exact_policy(enabled):
    config = {'mcp_servers': {'eodhd': {'url': 'http://mock/mcp',
               'tools': {'include': ['terminal'], 'resources': True}}},
              'model': {'default': 'unchanged'}}
    result = configure_tools(config, mcp_enabled=enabled)
    assert result['mcp_servers']['eodhd'] == {
        'url': 'http://mock/mcp', 'enabled': enabled,
        'tools': {'include': sorted(EODHD_TOOLS), 'resources': False, 'prompts': False}}
    assert result['model'] == {'default': 'unchanged'}
    validate_tools(BASE_TOOLS | MCP_TOOLS if enabled else BASE_TOOLS)


def test_profile_rejects_unregistered_server():
    with pytest.raises(ValueError, match='unexpected MCP server'):
        configure_tools({'mcp_servers': {'eodhd': {}, 'other': {}}}, mcp_enabled=True)
