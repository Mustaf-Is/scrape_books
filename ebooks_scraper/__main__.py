import argparse
import logging
from pathlib import Path

from playwright.sync_api import Error

from .config import PAGE_COUNT, TIMEOUT_MS, ScraperConfig
from .scraper import Scraper


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape eBooks.com mathematics books in a visible browser.")
    parser.add_argument("--pages", type=int, default=PAGE_COUNT, help="Number of listing pages (default: 3)")
    parser.add_argument("--output", type=Path, default=Path("books.csv"))
    parser.add_argument("--timeout-ms", type=int, default=TIMEOUT_MS)
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between book requests")
    parser.add_argument("--profile-dir", type=Path, default=Path(".browser-profile"), help="Dedicated Chromium session directory")
    args = parser.parse_args()
    try:
        config = ScraperConfig(args.pages, args.output, args.timeout_ms, args.delay, args.profile_dir)
    except ValueError as exc:
        parser.error(str(exc))
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    scraper = Scraper(config)
    try:
        count = scraper.run()
    except (Error, OSError, KeyboardInterrupt) as exc:
        logging.error("Scrape stopped: %s", exc)
        return 1
    logging.info("Saved %s rows to %s (%s failures)", count, config.output, scraper.failures)
    return 1 if scraper.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
