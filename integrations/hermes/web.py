"""Keyless HTML/text extraction using Hermes's connection-time SSRF guard."""
from datetime import datetime, timezone
from html.parser import HTMLParser
import time

import httpx


class PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.in_title = False
        self.title = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'):
            self.hidden += 1
        if tag == 'title':
            self.in_title = True

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript'):
            self.hidden = max(0, self.hidden - 1)
        if tag == 'title':
            self.in_title = False

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.text.append(data.strip())
            if self.in_title:
                self.title.append(data.strip())


def extract_pages(urls, *, client):
    if len(urls) > 5:
        raise ValueError('at most five URLs per extraction')
    pages = []
    for url in urls:
        page = dict(url=url, title='', content='', error=None)
        try:
            started = time.monotonic()
            with client.stream('GET', url) as response:
                response.raise_for_status()
                kind = response.headers.get('content-type', '').split(';')[0].lower()
                if kind not in ('text/html', 'application/xhtml+xml', 'text/plain'):
                    raise ValueError('only HTML and plain text supported; PDF/browser pages require another source')
                data = bytearray()
                for chunk in response.iter_bytes(chunk_size=16384):
                    if len(data) + len(chunk) > 2_000_000 or time.monotonic() - started > 30:
                        raise ValueError('page exceeds size/time limit')
                    data.extend(chunk)
                text = data.decode(response.encoding or 'utf-8', errors='replace')
                if kind != 'text/plain':
                    parser = PageText(); parser.feed(text)
                    text = '\n'.join(parser.text); page['title'] = ' '.join(parser.title)
                if not text.strip():
                    raise ValueError('page has no readable text')
                truncated = len(text) > 15000
                page['content'] = (f'Source URL: {response.url}\nRetrieved at: {datetime.now(timezone.utc).isoformat()}\n'
                                   'Publication date: verify in source text; not inferred from retrieval time.\n\n'
                                   + text[:15000] + ('\n[Truncated at 15000 characters]' if truncated else ''))
        except httpx.HTTPStatusError as exc:
            page['error'] = f'HTTP {exc.response.status_code}; page was not read'
        except httpx.HTTPError:
            page['error'] = 'Page fetch failed; page was not read'
        except ValueError as exc:
            page['error'] = str(exc)
        pages.append(page)
    return pages


def register_extract_provider(ctx):
    from agent.web_search_provider import WebSearchProvider
    from tools.url_safety import create_ssrf_safe_client

    class PublicPageProvider(WebSearchProvider):
        @property
        def name(self):
            return 'youwei-public-page'

        def is_available(self):
            return True

        def supports_search(self):
            return False

        def supports_extract(self):
            return True

        def extract(self, urls, **kwargs):
            with create_ssrf_safe_client(timeout=15, follow_redirects=True, max_redirects=5,
                                         trust_env=False, headers={'User-Agent':'YouweiResearch/1.0'}) as client:
                return extract_pages(urls, client=client)

    ctx.register_web_search_provider(PublicPageProvider())
