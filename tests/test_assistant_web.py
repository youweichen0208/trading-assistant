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
