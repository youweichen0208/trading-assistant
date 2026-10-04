"""Install deployment-owned profile configuration, then exec native gateway."""
import os
from pathlib import Path
from eodhd import EODHD_TOOLS, validate_tools, install_secret_redaction


def main():
    install_secret_redaction()
    for name in ('API_SERVER_KEY', 'YOUWEI_ASSISTANT_LLM_KEY', 'YOUWEI_ASSISTANT_CORE_KEY'):
        if len(os.environ.get(name, '')) < 16:
            raise SystemExit(f'{name} must be configured (at least 16 characters)')
    home = Path(os.environ['HERMES_HOME'])
    home.mkdir(parents=True, exist_ok=True)
    package = Path(__file__).parent
    from ruamel.yaml import YAML
    yaml = YAML()
    config = yaml.load((package / 'config.yaml').read_text())
    assert set(config['mcp_servers']) == {'eodhd'}, 'unexpected MCP server'
    assert set(config['mcp_servers']['eodhd']['tools']['include']) == EODHD_TOOLS, 'MCP allowlist drift'
    # Restore drills and offline deployments retain the original five tools.
    if not os.environ.get('EODHD_API_KEY'):
        config['mcp_servers']['eodhd']['enabled'] = False
    with (home / 'config.yaml').open('w') as stream:
        yaml.dump(config, stream)
    plugins = home / 'plugins'; plugins.mkdir(exist_ok=True)
    target = plugins / 'youwei-assistant'
    if not target.exists():
        target.symlink_to(package, target_is_directory=True)
    elif target.resolve() != package.resolve():
        raise SystemExit('unexpected assistant plugin directory')
    Path(os.environ['YOUWEI_KNOWLEDGE_DIR']).mkdir(parents=True, exist_ok=True)
    run_gateway()


def run_gateway():
    # Fail startup on missing base tools or tools outside the configured boundary.
    install_secret_redaction()
    from hermes_cli.plugins import discover_plugins
    from hermes_cli.config import load_config
    from hermes_cli.tools_config import _get_platform_tools
    from model_tools import get_tool_definitions
    discover_plugins()
    from tools.mcp_tool_discovery import discover_mcp_tools
    from tools.mcp_tool_lifecycle import shutdown_mcp_servers
    discover_mcp_tools(allowed_mcp_names=['eodhd'])
    names = {tool['function']['name'] for tool in get_tool_definitions(
        enabled_toolsets=sorted(_get_platform_tools(load_config(), 'api_server')), quiet_mode=True)}
    validate_tools(names)
    shutdown_mcp_servers()
    os.execvp('hermes', ['hermes', 'gateway', 'run'])


if __name__ == '__main__':
    main()
