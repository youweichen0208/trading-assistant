"""Profile installation and native discovery shared by startup and acceptance."""
import os
from contextlib import contextmanager
from pathlib import Path

if __package__:
    from .policy import EODHD_TOOLS, validate_tools
    from .eodhd import install_secret_redaction
else:
    from policy import EODHD_TOOLS, validate_tools
    from eodhd import install_secret_redaction


def configure_tools(config, *, mcp_enabled):
    """Apply the code-owned policy to a newly loaded profile template."""
    if set(config.get('mcp_servers', {})) != {'eodhd'}:
        raise ValueError('unexpected MCP server')
    server = config['mcp_servers']['eodhd']
    server['tools'] = {'include': sorted(EODHD_TOOLS), 'resources': False, 'prompts': False}
    server['enabled'] = mcp_enabled
    return config


def load_profile_config(*, mcp_enabled=None):
    from ruamel.yaml import YAML
    config = YAML(typ='safe').load(Path(__file__).with_name('config.yaml').read_text())
    return configure_tools(config, mcp_enabled=(bool(os.environ.get('EODHD_API_KEY'))
                                               if mcp_enabled is None else mcp_enabled))


def install_profile(home):
    from ruamel.yaml import YAML
    home = Path(home)
    home.mkdir(parents=True, exist_ok=True)
    package = Path(__file__).parent
    plugins = home / 'plugins'
    plugins.mkdir(exist_ok=True)
    target = plugins / 'youwei-assistant'
    if not target.exists():
        target.symlink_to(package, target_is_directory=True)
    elif target.resolve() != package.resolve():
        raise SystemExit('unexpected assistant plugin directory')
    with (home / 'config.yaml').open('w') as stream:
        YAML().dump(load_profile_config(), stream)


@contextmanager
def discovered_tools():
    """Yield validated native tools, always closing MCP discovery connections."""
    install_secret_redaction()
    from hermes_cli.plugins import discover_plugins
    from hermes_cli.config import load_config
    from hermes_cli.tools_config import _get_platform_tools
    from model_tools import get_tool_definitions
    from tools.mcp_tool_discovery import discover_mcp_tools
    from tools.mcp_tool_lifecycle import shutdown_mcp_servers
    try:
        discover_plugins()
        discover_mcp_tools(allowed_mcp_names=['eodhd'])
        names = {tool['function']['name'] for tool in get_tool_definitions(
            enabled_toolsets=sorted(_get_platform_tools(load_config(), 'api_server')),
            quiet_mode=True)}
        validate_tools(names)
        yield names
    finally:
        shutdown_mcp_servers()
