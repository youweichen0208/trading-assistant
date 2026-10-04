"""Install deployment-owned profile configuration, then exec native gateway."""
import os
from pathlib import Path

if __package__:
    from .bootstrap import install_profile, discovered_tools
    from .eodhd import install_secret_redaction
else:
    from bootstrap import install_profile, discovered_tools
    from eodhd import install_secret_redaction


def main():
    install_secret_redaction()
    for name in ('API_SERVER_KEY', 'YOUWEI_ASSISTANT_LLM_KEY', 'YOUWEI_ASSISTANT_CORE_KEY'):
        if len(os.environ.get(name, '')) < 16:
            raise SystemExit(f'{name} must be configured (at least 16 characters)')
    install_profile(os.environ['HERMES_HOME'])
    Path(os.environ['YOUWEI_KNOWLEDGE_DIR']).mkdir(parents=True, exist_ok=True)
    run_gateway()


def run_gateway():
    with discovered_tools():
        pass
    os.execvp('hermes', ['hermes', 'gateway', 'run'])


if __name__ == '__main__':
    main()
