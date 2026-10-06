import httpx

from integrations.hermes.web import extract_pages


def test_extract_returns_read_text_and_date_not_scripts():
    def handler(request):
        return httpx.Response(200, headers={'content-type':'text/html'}, text='<title>Company</title><script>SECRET()</script><p>Annual report</p>')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        page = extract_pages(['https://example.com/report'], client=client)[0]
    assert page['title'] == 'Company'
    assert 'Annual report' in page['content'] and 'SECRET' not in page['content']
    assert 'Retrieved at' in page['content']


def test_extract_binary_is_explicit_failure():
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, headers={'content-type':'application/pdf'}, content=b'%PDF'))) as client:
        page = extract_pages(['https://example.com/report.pdf'], client=client)[0]
    assert page['error'] and not page['content']


def test_extract_deduplicates_and_fetches_independent_pages_concurrently():
    import threading
    entered = threading.Barrier(2)
    calls = []
    def handler(request):
        calls.append(str(request.url))
        entered.wait(timeout=1)
        return httpx.Response(200, headers={'content-type':'text/html'}, text='<nav>MENU</nav><article><p>Evidence</p></article><footer>ADVERT</footer>')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        pages = extract_pages(['https://example.com/a', 'https://example.com/b', 'https://example.com/a'], client=client)
    assert len(calls) == 2 and len(pages) == 3
    assert all(p['error'] is None and 'Evidence' in p['content'] and 'MENU' not in p['content'] and 'ADVERT' not in p['content'] for p in pages)


def test_batch_search_deduplicates_and_runs_in_parallel():
    from integrations.hermes.research import search_batch
    import threading
    barrier = threading.Barrier(2)
    def search(query, limit):
        barrier.wait(timeout=1)
        return '{"success": true}'
    result = search_batch(['earnings AAPL', 'product AAPL', ' earnings AAPL '], search=search)
    assert len(result['results']) == 2
    assert all(r['result']['success'] for r in result['results'])


def test_cancelled_batch_starts_no_fetches(monkeypatch):
    from integrations.hermes import web, research
    monkeypatch.setattr(web,'interrupted',lambda:True)
    monkeypatch.setattr(research,'interrupted',lambda:True)
    def fail(*args,**kwargs): raise AssertionError('unexpected network')
    with httpx.Client(transport=httpx.MockTransport(fail)) as client:
        pages=web.extract_pages(['https://example.com/a'],client=client)
    assert 'cancelled' in pages[0]['error']
    assert research.search_batch(['query'],search=fail)['results'][0]['result']=={'error':'cancelled'}


def test_one_page_failure_does_not_discard_other_evidence():
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(503) if r.url.path=='/bad' else httpx.Response(200,headers={'content-type':'text/plain'},text='Evidence'))) as client:
        pages=extract_pages(['https://example.com/bad','https://example.com/good'],client=client)
    assert pages[0]['error'] and 'Evidence' in pages[1]['content']
