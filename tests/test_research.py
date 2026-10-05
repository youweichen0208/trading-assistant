import json
from integrations.hermes.handlers import tool_boundary


def test_delegation_is_restricted_before_native_dispatch():
    seen=[]
    result=tool_boundary(tool_name='delegate_task',args={'tasks':[{'goal':'Verify Apple earnings from sources','toolsets':['terminal'],'role':'orchestrator'}]},next_call=lambda args: seen.append(args) or '{}',session_id='restricted',turn_id='turn')
    assert seen, result
    assert 'toolsets' not in seen[0]['tasks'][0]
    assert seen[0]['tasks'][0]['role']=='leaf'
    again=tool_boundary(tool_name='delegate_task',args={'goal':'Do another investigation'},next_call=lambda _: 'bad',session_id='restricted',turn_id='turn')
    assert 'error' in json.loads(again)


def test_child_permissions_and_budgets_fail_closed(monkeypatch):
    from integrations.hermes import research
    monkeypatch.setattr(research, 'is_child', lambda: True)
    seen=[]
    def call(name, args={}):
        return tool_boundary(tool_name=name,args=args,next_call=lambda args:seen.append(args) or '{}',session_id='child-budget',turn_id='t')
    for name in ('terminal','memory','youwei_platform','delegate_task','web_search_batch'):
        assert 'denied' in call(name)
    assert call('web_search') == '{}'
    assert call('web_search') == '{}'
    assert 'denied' in call('web_search')
    assert call('web_extract', {'urls':['https://example.com']*5}) == '{}'
    assert 'denied' in call('web_extract', {'urls':['https://example.com']})
    assert len(seen)==3


def test_invalid_delegation_never_dispatches():
    for args in ({'tasks':[{'goal':'valid research task'}]*3}, {'action':'steer','goal':'valid research task'}, {'goal':'short'}):
        result=tool_boundary(tool_name='delegate_task',args=args,next_call=lambda _: (_ for _ in ()).throw(AssertionError('dispatched')),session_id='invalid',turn_id='t')
        assert 'error' in json.loads(result)


def test_child_discovery_is_filtered_without_changing_parent(monkeypatch):
    from integrations.hermes import research
    request={'tools':[{'type':'function','function':{'name':name}} for name in ('web_search','web_extract','youwei_platform','terminal')]}
    monkeypatch.setattr(research,'is_child',lambda:False)
    assert research.restrict_child_request(request=request) is None
    monkeypatch.setattr(research,'is_child',lambda:True)
    result=research.restrict_child_request(request=request)['request']
    assert [t['function']['name'] for t in result['tools']]==['web_search','web_extract']
    assert len(request['tools'])==4


import pytest
@pytest.mark.parametrize('cancelled', [False, True])
def test_parent_stop_or_deadline_interrupts_children_and_joins_monitor(monkeypatch, cancelled):
    import threading
    from integrations.hermes import research
    stopped=threading.Event()
    calls=[]
    monkeypatch.setattr(research,'interrupted',lambda:cancelled)
    monkeypatch.setattr(research,'RESEARCH_TIMEOUT_SECONDS',0.01)
    monkeypatch.setattr(research,'interrupt_owned_children',lambda session:(calls.append(session),stopped.set()))
    def dispatch(args):
        assert stopped.wait(1)
        return '{}'
    assert research.delegate({'goal':'Verify this public event'},dispatch,'cancel-'+str(cancelled),'turn')=='{}'
    assert calls==['cancel-'+str(cancelled)]
