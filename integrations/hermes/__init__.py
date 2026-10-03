"""Hermes native plugin, loaded only in the personal assistant profile."""
import contextvars
import json
import os
from pathlib import Path

from .knowledge import KnowledgeStore
from .core_client import PlatformClient

_identity = contextvars.ContextVar('youwei_call_identity', default=None)
ALLOWED_TOOLS = frozenset({'web_search', 'web_extract', 'memory', 'youwei_platform', 'youwei_knowledge'})


def tool_boundary(*, tool_name, args, next_call, session_id=None, turn_id=None, tool_call_id=None, **kwargs):
    if tool_name not in ALLOWED_TOOLS:
        return json.dumps({'error': 'tool is not allowed in the personal assistant'})
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


def _schema(name, description, actions, properties):
    return dict(name=name, description=description, parameters={
        'type': 'object', 'properties': {
            'action': {'type': 'string', 'enum': actions},
            'arguments': {'type': 'object', 'properties': properties, 'additionalProperties': False},
        }, 'required': ['action', 'arguments'], 'additionalProperties': False})


def register(ctx):
    from .web import register_extract_provider
    register_extract_provider(ctx)
    ctx.register_middleware('tool_execution', tool_boundary)
    ctx.register_system_prompt_section('youwei.personal-assistant', Path(__file__).with_name('instructions.txt').read_text(), max_chars=4000)
    ctx.register_tool(name='youwei_platform', toolset='youwei-assistant', handler=platform_handler,
        schema=_schema('youwei_platform',
            'Call the research platform. daily_bars: ticker/start_date/end_date, optional timezone-aware as_of. '
            'submit: ticker/horizon_td (1,20,60), optional benchmark_ticker; no free-text question. '
            'list: optional limit. status/report/cancel: research_id; report optionally version. '
            'Report access is tenant-scoped; cancel only on explicit user request. Daily bars are not live quotes.',
            ['daily_bars', 'submit', 'list', 'status', 'report', 'cancel'],
            {**{k: {'type': 'string'} for k in ('ticker', 'start_date', 'end_date', 'as_of', 'benchmark_ticker', 'research_id')},
             **{k: {'type': 'integer'} for k in ('horizon_td', 'version', 'limit')}}))
    ctx.register_tool(name='youwei_knowledge', toolset='youwei-assistant', handler=knowledge_handler,
        schema=_schema('youwei_knowledge',
            'Personal notes outside the formal Ledger. save requires note_id/title/content/sources; '
            'read requires note_id; search takes query and optional limit. '
            'revise requires note_id/content/expected_sha256 and optional sources; '
            'delete requires note_id/expected_sha256. Read current hash before revising/deleting. '
            'Each source has url/accessed_at/published_at (null if unknown). Empty sources for personal methods only. '
            'Max 256 KB per note, 2000 notes; flat IDs only. Search and read across new chats.',
            ['save', 'read', 'search', 'revise', 'delete'],
            {**{k: {'type': 'string'} for k in ('note_id', 'title', 'content', 'expected_sha256', 'query')},
             'limit': {'type': 'integer'}, 'sources': {'type': 'array', 'items': {'type': 'object', 'properties': {
                 'url': {'type': 'string'}, 'accessed_at': {'type': 'string'},
                 'published_at': {'type': ['string', 'null']}
             }, 'required': ['url', 'accessed_at']}}}))
