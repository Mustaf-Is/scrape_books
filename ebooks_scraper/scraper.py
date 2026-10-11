import logging
import time
from collections.abc import Iterator

from playwright.sync_api import BrowserContext, Error, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from .config import ScraperConfig, listing_url
from .export import write_csv
from .models import Book
from .parsing import LISTING_LINK_SELECTOR, extract_book_urls, parse_book

logger = logging.getLogger(__name__)

# Wait for Vue to render valid links rather than its empty template elements.
LISTING_READY = """selector => Array.from(document.querySelectorAll(selector))
    .some(a => /\\/en-us\\/book\\/\\d+\\//.test(a.getAttribute('href') || ''))"""
# The heading can arrive before product metadata, so wait for the details-table
# title when that field exists. Missing optional metadata is allowed.
BOOK_READY = """() => {
    const title = document.querySelector('h1#main-content[itemprop="name"]');
    if (!title || !title.textContent.trim()) return false;
    const tables = document.querySelectorAll('dl.book-details');
    if (!tables.length) return true;
    const titles = Array.from(tables).flatMap(table => Array.from(table.querySelectorAll('dt')))
        .filter(dt => dt.textContent.trim().toLowerCase().replace(/:$/, '') === 'title');
    return !titles.length || titles.some(dt => dt.nextElementSibling?.tagName === 'DD'
        && dt.nextElementSibling.textContent.trim());
}"""

CHALLENGE_FINISHED = """() => {
    const title = document.title.toLowerCase();
    return !title.includes('just a moment')
        && !document.querySelector('#challenge-running, #challenge-stage, #challenge-form')
        && Boolean(document.body?.innerText.trim());
}"""


def navigate(page: Page, url: str) -> None:
    response = page.goto(url, wait_until="domcontentloaded")
    if response and response.headers.get("cf-mitigated") == "challenge":
        # Cloudflare can return 403 while ordinary browser verification is
        # still running. Keep this tab and context alive to receive its cookies.
        logger.warning("Security verification at %s; waiting in the visible Chromium window", url)
        try:
            page.wait_for_function(CHALLENGE_FINISHED)
        except PlaywrightTimeoutError as exc:
            raise RuntimeError(
                f"Security verification did not finish for {url}. "
                "Complete any prompt in the Chromium window or increase --timeout-ms."
            ) from exc
        # The initial response describes the challenge, not the page reached
        # after verification. The caller now waits for the actual book content.
        return
    if response and response.status >= 400:
        raise RuntimeError(f"HTTP {response.status} while loading {url}")


class Scraper:
    def __init__(self, config: ScraperConfig):
        self.config = config
        self.failures = 0

    def books(self, context: BrowserContext) -> Iterator[Book]:
        seen: set[str] = set()
        listing = context.new_page()
        try:
            for number in range(1, self.config.page_count + 1):
                url = listing_url(number)
                logger.info("Listing page %s/%s: %s", number, self.config.page_count, url)
                try:
                    navigate(listing, url)
                    listing.wait_for_function(LISTING_READY, arg=LISTING_LINK_SELECTOR)
                    urls = extract_book_urls(listing.content(), url)
                    if not urls:
                        raise RuntimeError("No book URLs found after rendering")
                except (Error, RuntimeError) as exc:
                    self.failures += 1
                    logger.error("Listing page failed: %s", exc)
                    continue
                for book_url in urls:
                    if book_url in seen:
                        continue
                    seen.add(book_url)
                    time.sleep(self.config.delay_seconds)
                    # Each book gets a fresh tab in the same browser context.
                    detail = context.new_page()
                    try:
                        navigate(detail, book_url)
                        detail.wait_for_function(BOOK_READY)
                        book = parse_book(detail.content(), book_url)
                        logger.info("Scraped: %s", book.title)
                    except (Error, RuntimeError) as exc:
                        self.failures += 1
                        logger.error("Book failed %s: %s", book_url, exc)
                        book = Book(url=book_url)
                    finally:
                        detail.close()
                    yield book
        finally:
            listing.close()

    def run(self) -> int:
        with sync_playwright() as playwright:
            # A dedicated scraper profile preserves ordinary verification
            # cookies between runs without touching the user's browser profile.
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.config.profile_dir.resolve()),
                channel="chromium",
                headless=False,
                locale="en-US",
                viewport={"width": 1280, "height": 900},
            )
            logger.info("Browser: Chromium (visible); profile: %s", self.config.profile_dir.resolve())
            try:
                context.set_default_timeout(self.config.timeout_ms)
                context.set_default_navigation_timeout(self.config.timeout_ms)
                return write_csv(self.books(context), self.config.output)
            finally:
                context.close()
