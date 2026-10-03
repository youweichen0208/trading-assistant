"""Install deployment-owned profile configuration, then exec native gateway."""
import os
from pathlib import Path
import shutil


def main():
    for name in ('API_SERVER_KEY', 'YOUWEI_ASSISTANT_LLM_KEY', 'YOUWEI_ASSISTANT_CORE_KEY'):
        if len(os.environ.get(name, '')) < 16:
            raise SystemExit(f'{name} must be configured (at least 16 characters)')
    home = Path(os.environ['HERMES_HOME'])
    home.mkdir(parents=True, exist_ok=True)
    package = Path(__file__).parent
    shutil.copyfile(package / 'config.yaml', home / 'config.yaml')
    plugins = home / 'plugins'; plugins.mkdir(exist_ok=True)
    target = plugins / 'youwei-assistant'
    if not target.exists():
        target.symlink_to(package, target_is_directory=True)
    elif target.resolve() != package.resolve():
        raise SystemExit('unexpected assistant plugin directory')
    Path(os.environ['YOUWEI_KNOWLEDGE_DIR']).mkdir(parents=True, exist_ok=True)
    # Fail startup if plugin/config loading would silently drop the intended tool boundary.
    from hermes_cli.plugins import discover_plugins
    from hermes_cli.config import load_config
    from hermes_cli.tools_config import _get_platform_tools
    from model_tools import get_tool_definitions
    discover_plugins()
    names = {tool['function']['name'] for tool in get_tool_definitions(
        enabled_toolsets=sorted(_get_platform_tools(load_config(), 'api_server')), quiet_mode=True)}
    if names != {'web_search', 'web_extract', 'memory', 'youwei_platform', 'youwei_knowledge'}:
        raise SystemExit('assistant tool allowlist did not load exactly')
    os.execvp('hermes', ['hermes', 'gateway', 'run'])


if __name__ == '__main__':
    main()
