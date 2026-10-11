"""Offline integration tests using a visible Chromium browser and intercepted HTML."""

from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from ebooks_scraper.config import CATEGORY_URL, ScraperConfig, listing_url
from ebooks_scraper.scraper import Scraper, navigate

BASE = "https://www.ebooks.com"
FIRST = BASE + "/en-us/book/123/first/author/"
SECOND = BASE + "/en-us/book/456/second/author/"
HTML = (Path(__file__).parent / "fixtures" / "book.html").read_text(encoding="utf-8")


@pytest.fixture
def context():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chromium", headless=False)
        ctx = browser.new_context()
        ctx.set_default_timeout(2000)
        try:
            yield ctx
        finally:
            browser.close()


def listing(*urls):
    return '<ul aria-label="Search results">' + "".join(
        f'<li class="searchresult"><a href="{url}">Title</a><a href="{url}">Cover</a></li>'
        for url in urls
    ) + "</ul>"


def test_pagination_dynamic_rendering_and_new_tabs(context, tmp_path):
    scraper = Scraper(ScraperConfig(page_count=3, output=tmp_path / "books.csv", delay_seconds=0))
    requested = []
    pages = []
    context.on("page", lambda page: pages.append(page))
    responses = {
        listing_url(1): listing(FIRST),
        listing_url(2): listing(FIRST, SECOND),
        listing_url(3): listing(SECOND),
        FIRST: HTML,
        SECOND: '<h1 id="main-content" itemprop="name">Second</h1>',
    }

    def handler(route):
        requested.append(route.request.url)
        body = responses[route.request.url]
        if route.request.url.startswith(CATEGORY_URL):
            # Initially empty: links must be collected after client rendering.
            import json
            body = '<body><script>setTimeout(() => document.body.innerHTML = ' + json.dumps(body) + ', 50)</script></body>'
        route.fulfill(status=200, content_type="text/html", body=body)

    context.route("**/*", handler)
    books = list(scraper.books(context))
    assert [book.url for book in books] == [FIRST, SECOND]
    assert books[0].isbns == "9781119002260; 9781119002253; 9781119002062"
    assert books[1].publisher == "N/A"
    assert requested == [listing_url(1), FIRST, listing_url(2), SECOND, listing_url(3)]
    assert len(pages) == 3  # One listing tab and a separate tab for each unique book.
    assert all(page.is_closed() for page in pages)
    assert scraper.failures == 0


def test_initial_cloudflare_403_can_finish_in_same_tab(context):
    requests = []

    def handler(route):
        requests.append(route.request.url)
        if len(requests) == 1:
            route.fulfill(
                status=403,
                headers={"cf-mitigated": "challenge"},
                content_type="text/html",
                body='''<title>Just a moment...</title><body><form id="challenge-form">Verifying</form>
                <script>setTimeout(() => location.reload(), 100)</script></body>''',
            )
        else:
            route.fulfill(status=200, content_type="text/html", body=listing(FIRST))

    context.route("**/*", handler)
    page = context.new_page()
    navigate(page, listing_url(1))
    assert len(requests) == 2
    assert page.locator('li.searchresult').count() == 1


def test_unresolved_challenge_has_actionable_error(context):
    context.route("**/*", lambda route: route.fulfill(
        status=403, headers={"cf-mitigated": "challenge"}, content_type="text/html",
        body='<title>Just a moment...</title><form id="challenge-form">Verifying</form>',
    ))
    page = context.new_page()
    page.set_default_timeout(200)
    with pytest.raises(RuntimeError, match="Security verification did not finish"):
        navigate(page, listing_url(1))


def test_failed_book_preserves_row_and_continues(context):
    scraper = Scraper(ScraperConfig(page_count=1, delay_seconds=0))

    def handler(route):
        url = route.request.url
        if url == listing_url(1):
            route.fulfill(status=200, content_type="text/html", body=listing(FIRST, SECOND))
        elif url == FIRST:
            route.fulfill(status=503, body="Unavailable")
        else:
            route.fulfill(status=200, content_type="text/html", body=HTML)

    context.route("**/*", handler)
    books = list(scraper.books(context))
    assert len(books) == 2
    assert books[0].url == FIRST
    assert books[0].title == "N/A"
    assert books[1].title == "Storytelling with Data"
    assert scraper.failures == 1
    assert context.pages == []


def test_failed_listing_continues_to_next_page(context):
    scraper = Scraper(ScraperConfig(page_count=2, delay_seconds=0))

    def handler(route):
        if route.request.url == listing_url(1):
            route.fulfill(status=403, body="Forbidden")
        elif route.request.url == listing_url(2):
            route.fulfill(status=200, content_type="text/html", body=listing(SECOND))
        else:
            route.fulfill(status=200, content_type="text/html", body=HTML)

    context.route("**/*", handler)
    books = list(scraper.books(context))
    assert [book.url for book in books] == [SECOND]
    assert scraper.failures == 1
    assert context.pages == []


def test_waits_for_delayed_product_metadata(context):
    scraper = Scraper(ScraperConfig(page_count=1, delay_seconds=0))
    delayed = '''<h1 id="main-content" itemprop="name">Book</h1>
    <dl class="book-details"><dt>Title</dt><dd id="title"></dd>
    <dt>Publisher</dt><dd id="publisher"></dd></dl>
    <script>setTimeout(() => {
        document.querySelector('#title').textContent = 'Book';
        document.querySelector('#publisher').textContent = 'Delayed Press';
    }, 100);</script>'''

    def handler(route):
        body = listing(FIRST) if route.request.url == listing_url(1) else delayed
        route.fulfill(status=200, content_type="text/html", body=body)

    context.route("**/*", handler)
    books = list(scraper.books(context))
    assert books[0].publisher == "Delayed Press"
    assert books[0].price == "N/A"
    assert scraper.failures == 0
