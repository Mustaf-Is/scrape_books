from pathlib import Path

import pytest

from ebooks_scraper.config import CATEGORY_URL, PAGE_COUNT, ScraperConfig, listing_url
from ebooks_scraper.models import MISSING
from ebooks_scraper.parsing import extract_book_urls, parse_book

BOOK_URL = "https://www.ebooks.com/en-us/book/123/example/author/"
FIXTURE = Path(__file__).parent / "fixtures" / "book.html"


def test_extracts_requested_fields():
    book = parse_book(FIXTURE.read_text(encoding="utf-8"), BOOK_URL)
    assert book.title == "Storytelling with Data"
    assert book.price == "US$41.95"
    assert book.publisher == "Wiley"
    assert book.published_date == "October 2015"
    assert book.isbns == "9781119002260; 9781119002253; 9781119002062"
    assert book.authors == "Cole Nussbaumer Knaflic"
    assert book.url == BOOK_URL


def test_missing_fields_are_na():
    book = parse_book('<h1 id="main-content" itemprop="name">Only title</h1>', BOOK_URL)
    assert book.title == "Only title"
    assert {book.price, book.publisher, book.published_date, book.isbns, book.authors} == {MISSING}


def test_all_fields_missing():
    row = parse_book("<html></html>", BOOK_URL).csv_row()
    assert all(value == MISSING for key, value in row.items() if key != "url")


@pytest.mark.parametrize("label", ["Author", "Authors", "Author(s)"])
def test_multiple_authors(label):
    html = f'''<dl class="book-details"><dt>{label}</dt>
    <dd><a class="author-link">Alice Example</a>; <a class="author-link">Bob Example</a></dd>
    <dd><a class="author-link">Alice Example</a></dd><dt>Publisher</dt><dd>Press</dd></dl>'''
    book = parse_book(html, BOOK_URL)
    assert book.authors == "Alice Example; Bob Example"
    assert book.publisher == "Press"


def test_link_scope_deduplication_and_normalization():
    html = '''<a href="/en-us/book/999/unrelated/">Unrelated</a>
    <ul aria-label="Search results"><li class="searchresult tile book-details">
    <a href="/en-us/book/123/example/author/">Cover</a>
    <a href="/en-us/book/123/example/author/?source=title#main">Title</a>
    <a href="/en-us/author/123/">Author</a><a href="/cart/add/123/">Cart</a>
    <a href="https://outside.example/en-us/book/123/example/">Outside</a>
    <a href="/en-us/book/456/second/author/">Second</a></li></ul>'''
    assert extract_book_urls(html) == [BOOK_URL, "https://www.ebooks.com/en-us/book/456/second/author/"]


def test_sale_price_and_mobile_fallback():
    html = '''<div id="price-mobile"><div class="price"><del>US$50.00</del>
    <span>US$35.00</span><span class="sr-only">Sale price: USD 35.00</span></div></div>'''
    assert parse_book(html, BOOK_URL).price == "US$35.00"


def test_title_fallback_and_whitespace():
    book = parse_book('<dl class="book-details"><dt>Title:</dt><dd> A\n Book </dd></dl>', BOOK_URL)
    assert book.title == "A Book"


def test_pagination_default():
    assert PAGE_COUNT == 3
    assert ScraperConfig().page_count == 3
    assert listing_url(1) == CATEGORY_URL
    assert listing_url(3) == CATEGORY_URL + "?pageNumber=3"


@pytest.mark.parametrize("kwargs", [{"page_count": 0}, {"timeout_ms": 0}, {"delay_seconds": -1}])
def test_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        ScraperConfig(**kwargs)
