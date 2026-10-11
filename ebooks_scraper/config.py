from dataclasses import dataclass
from pathlib import Path

CATEGORY_URL = "https://www.ebooks.com/en-us/category/mathematics/5418/"
# Scrape listing pages 1 through PAGE_COUNT, inclusive.
PAGE_COUNT = 3
TIMEOUT_MS = 30_000


@dataclass(frozen=True)
class ScraperConfig:
    page_count: int = PAGE_COUNT
    output: Path = Path("books.csv")
    timeout_ms: int = TIMEOUT_MS
    delay_seconds: float = 1.0
    profile_dir: Path = Path(".browser-profile")

    def __post_init__(self) -> None:
        if self.page_count < 1:
            raise ValueError("page_count must be at least 1")
        if self.timeout_ms <= 0:
            raise ValueError("timeout_ms must be positive")
        if self.delay_seconds < 0:
            raise ValueError("delay_seconds cannot be negative")


def listing_url(page_number: int) -> str:
    if page_number < 1:
        raise ValueError("page_number must be at least 1")
    # The category landing URL is page 1; use its normal entry point before
    # navigating to subsequent pages in the established browser session.
    return CATEGORY_URL if page_number == 1 else f"{CATEGORY_URL}?pageNumber={page_number}"
