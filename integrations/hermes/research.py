"""Bounded parallel web work and native delegation policy; no extra agent runtime."""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
import json
import threading
import time
from .finance import interrupted

_LOCK=threading.Lock()
_BUDGETS=OrderedDict()
RESEARCH_TIMEOUT_SECONDS = 90

def interrupt_owned_children(session):
    from tools.delegate_tool_registry import list_active_subagents, interrupt_subagent
    for child in list_active_subagents():
        if child.get("owner_agent_session_id") == session:
            interrupt_subagent(child["subagent_id"])


def is_child():
    try:
        from agent.delegation_context import is_delegated_child_context
        return is_delegated_child_context()
    except ImportError:
        return False


def charge(identity, kind, amount, limit):
    if not identity:
        return False
    key=(identity,kind)
    with _LOCK:
        previous, timestamp=_BUDGETS.get(key,(0,0))
        if time.monotonic()-timestamp>600: previous=0
        if previous+amount>limit:return False
        _BUDGETS[key]=(previous+amount,time.monotonic());_BUDGETS.move_to_end(key)
        while len(_BUDGETS)>1024:_BUDGETS.popitem(last=False)
    return True


def child_allowed(name,args,session):
    if name=='web_search': return charge(session,'search',1,2)
    if name=='web_extract':
        urls=args.get('urls',[])
        return isinstance(urls,list) and 0<len(urls)<=5 and charge(session,'pages',len(urls),5)
    return False


def search_batch(queries, *, search=None):
    if not isinstance(queries,list) or not 1<=len(queries)<=3 or any(not isinstance(q,str) or not q.strip() or len(q)>500 for q in queries):
        return {'error':'provide_one_to_three_bounded_queries'}
    if search is None:
        from tools.web_tools import web_search_tool
        search=web_search_tool
    unique=list(dict.fromkeys(' '.join(q.split()) for q in queries))
    def one(query):
        if interrupted():return {'query':query,'result':{'error':'cancelled'}}
        try: result=json.loads(search(query,limit=3))
        except Exception:result={'error':'search_failed'}
        return {'query':query,'result':result}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures=[pool.submit(copy_context().run,one,q) for q in unique]
        return {'results':[f.result() for f in futures]}


def delegate(args,next_call,session,turn):
    tasks=args.get('tasks') or ([{'goal':args.get('goal'),'context':args.get('context','')}] if args.get('goal') else [])
    if args.get('action','spawn')!='spawn' or not isinstance(tasks,list) or not 1<=len(tasks)<=2:
        return json.dumps({'error':'use_one_batch_of_one_or_two_web_research_tasks'})
    safe=[]
    for task in tasks:
        if not isinstance(task,dict) or not isinstance(task.get('goal'),str) or not 10<=len(task['goal'])<=1200 or not isinstance(task.get('context',''),str) or len(task.get('context',''))>4000:
            return json.dumps({'error':'invalid_research_task'})
        safe.append({'goal':task['goal']+'\n仅核实此事件。最多2次搜索、5个原文页面。返回简短证据摘要、实际读取的来源URL/日期、未知和矛盾；不得将时间相关当因果；不要继续扩题。',
                     'context':task.get('context',''),'role':'leaf'})
    if not session or not turn or not charge((session,turn),'delegation',1,1):
        return json.dumps({'error':'one_research_batch_per_turn'})
    finished=threading.Event()
    def monitor():
        deadline=time.monotonic()+RESEARCH_TIMEOUT_SECONDS
        while not finished.wait(.1):
            if time.monotonic()<deadline and not interrupted():continue
            interrupt_owned_children(session)
    watcher=threading.Thread(target=copy_context().run,args=(monitor,),daemon=True)
    watcher.start()
    try:
        return next_call({'tasks':safe,'background':False,'role':'leaf'})
    finally:
        finished.set();watcher.join(timeout=1)


def register_research(ctx):
    ctx.register_tool(name='web_search_batch',toolset='youwei-assistant',
        handler=lambda args,**kwargs:json.dumps(search_batch(args.get('queries')),ensure_ascii=False),
        schema={'name':'web_search_batch','description':'Search up to three independent topics concurrently; duplicate queries are deduplicated. For simple lookups prefer this over subagents.',
                'parameters':{'type':'object','properties':{'queries':{'type':'array','items':{'type':'string','maxLength':500},'minItems':1,'maxItems':3}},'required':['queries'],'additionalProperties':False}})


def restrict_child_request(*, request, **kwargs):
    """Native children inherit toolsets; narrow discovery as well as execution."""
    if not is_child():
        return None
    result = dict(request)
    result['tools'] = [tool for tool in request.get('tools', [])
                       if tool.get('function', {}).get('name') in {'web_search', 'web_extract'}]
    return {'request': result}
