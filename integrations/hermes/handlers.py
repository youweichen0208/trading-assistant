"""Hermes native plugin, loaded only in the personal assistant profile."""
import contextvars
import json
import os

from .knowledge import KnowledgeStore
from .core_client import PlatformClient
from .eodhd import execute_query
from .policy import BASE_TOOLS, MCP_TOOLS

_identity = contextvars.ContextVar('youwei_call_identity', default=None)
ALLOWED_TOOLS = BASE_TOOLS | MCP_TOOLS


def tool_boundary(*, tool_name, args, next_call, session_id=None, turn_id=None, tool_call_id=None, **kwargs):
    if tool_name not in ALLOWED_TOOLS:
        return json.dumps({'error': 'tool is not allowed in the personal assistant'})
    if tool_name in MCP_TOOLS:
        return execute_query(tool_name, args, next_call)
    token = _identity.set((session_id, turn_id, tool_call_id))
    try:
        return next_call(args)
    finally:
        _identity.reset(token)


def platform_handler(args, **kwargs):
    try:
        client = PlatformClient(os.environ['YOUWEI_ASSISTANT_CORE_URL'], os.environ['YOUWEI_ASSISTANT_CORE_KEY'],
                                dashboard_url=os.environ.get('YOUWEI_ASSISTANT_DASHBOARD_URL', 'https://dash.youwei-agent.com'))
        return json.dumps(client.call(args['action'], args.get('arguments', {}), identity=_identity.get()), ensure_ascii=False)
    except (KeyError, ValueError, TypeError):
        return json.dumps({'error': 'invalid platform arguments or missing runtime configuration/identity'})


def knowledge_handler(args, **kwargs):
    try:
        store = KnowledgeStore(os.environ['YOUWEI_KNOWLEDGE_DIR'])
        action = args['action']
        if action not in {'save', 'read', 'search', 'revise', 'delete'}:
            raise ValueError('unknown knowledge operation')
        return json.dumps(getattr(store, action)(**args.get('arguments', {})), ensure_ascii=False)
    except (KeyError, ValueError, TypeError, OSError):
        return json.dumps({'error': 'knowledge operation rejected: check ID, required fields, size, existence and current hash'})


