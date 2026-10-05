"""Native plugin registration; handlers and tool policy are maintained separately."""
from pathlib import Path
from .eodhd import install_secret_redaction
from .handlers import tool_boundary, platform_handler, knowledge_handler


def _schema(name, description, actions, properties):
    return dict(name=name, description=description, parameters={
        'type': 'object', 'properties': {
            'action': {'type': 'string', 'enum': actions},
            'arguments': {'type': 'object', 'properties': properties, 'additionalProperties': False},
        }, 'required': ['action', 'arguments'], 'additionalProperties': False})


def register(ctx):
    install_secret_redaction()
    from .finance import register_finance
    register_finance(ctx)
    from .research import register_research, restrict_child_request
    register_research(ctx)
    ctx.register_middleware('llm_request', restrict_child_request)
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
