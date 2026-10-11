"""Pure HTML extraction; browser navigation lives in scraper.py."""

import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag

from .config import CATEGORY_URL
from .models import Book, MISSING

LISTING_LINK_SELECTOR = 'ul[aria-label="Search results"] li.searchresult a[href*="/book/"]'
TITLE_SELECTOR = 'h1#main-content[itemprop="name"]'


def clean_text(element: Tag | None) -> str:
    return " ".join(element.get_text(" ", strip=True).split()) if element else ""


def unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def extract_book_urls(html: str, base_url: str = CATEGORY_URL) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls = []
    origin = urlsplit(base_url)
    for anchor in soup.select(LISTING_LINK_SELECTOR):
        absolute = urlsplit(urljoin(base_url, str(anchor.get("href", ""))))
        if absolute.scheme not in {"http", "https"} or absolute.netloc != origin.netloc:
            continue
        if not re.fullmatch(r"/en-us/book/\d+/.*", absolute.path):
            continue
        urls.append(urlunsplit((absolute.scheme, absolute.netloc, absolute.path, "", "")))
    return unique(urls)


def extract_details(soup: BeautifulSoup) -> dict[str, list[Tag]]:
    """Group each dt with every following dd up to the next dt."""
    details: dict[str, list[Tag]] = {}
    for table in soup.select("dl.book-details"):
        label = ""
        for child in table.find_all(["dt", "dd"], recursive=False):
            if child.name == "dt":
                label = clean_text(child).rstrip(":").casefold()
                details.setdefault(label, [])
            elif label:
                details[label].append(child)
    return details


def extract_price(soup: BeautifulSoup) -> str:
    for selector in ("#price-tablet", "#price", "#price-mobile"):
        container = soup.select_one(selector)
        if not container:
            continue
        # Prefer the current price, excluding struck-through list prices and
        # duplicate screen-reader announcements.
        prices = container.select("div.price") or [container]
        for price in prices:
            fragment = BeautifulSoup(str(price), "html.parser")
            for unwanted in fragment.select(".sr-only, del, s, .list-price"):
                unwanted.decompose()
            value = clean_text(fragment)
            if value:
                return value
    return MISSING


def parse_book(html: str, url: str) -> Book:
    soup = BeautifulSoup(html, "html.parser")
    details = extract_details(soup)

    def values(*labels: str) -> str:
        return "; ".join(unique([
            clean_text(dd) for label in labels for dd in details.get(label, [])
        ])) or MISSING

    author_nodes = [
        dd for label in ("author", "authors", "author(s)") for dd in details.get(label, [])
    ]
    author_names = []
    for dd in author_nodes:
        links = dd.select("a.author-link, a[href*='/author/']")
        author_names.extend([clean_text(link) for link in links] if links else [clean_text(dd)])

    return Book(
        url=url,
        title=clean_text(soup.select_one(TITLE_SELECTOR)) or values("title"),
        price=extract_price(soup),
        published_date=values("published", "published date"),
        publisher=values("publisher"),
        isbns=values("isbns", "isbn"),
        authors="; ".join(unique(author_names)) or MISSING,
    )
