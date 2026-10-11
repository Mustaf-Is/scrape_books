import csv
from unittest.mock import MagicMock

from ebooks_scraper.config import ScraperConfig
from ebooks_scraper.models import Book
from ebooks_scraper.scraper import Scraper


def test_run_uses_visible_persistent_chromium_and_closes_context(monkeypatch, tmp_path):
    playwright = MagicMock()
    manager = MagicMock()
    manager.__enter__.return_value = playwright
    monkeypatch.setattr("ebooks_scraper.scraper.sync_playwright", lambda: manager)
    config = ScraperConfig(output=tmp_path / "books.csv", profile_dir=tmp_path / "profile")
    scraper = Scraper(config)
    monkeypatch.setattr(scraper, "books", lambda context: iter([Book(url="https://example.com/book")]))
    assert scraper.run() == 1
    playwright.chromium.launch_persistent_context.assert_called_once_with(
        user_data_dir=str(config.profile_dir.resolve()), channel="chromium", headless=False,
        locale="en-US", viewport={"width": 1280, "height": 900},
    )
    context = playwright.chromium.launch_persistent_context.return_value
    context.set_default_timeout.assert_called_once_with(config.timeout_ms)
    context.close.assert_called_once()
    with config.output.open(encoding="utf-8-sig", newline="") as handle:
        assert next(csv.DictReader(handle))["title"] == "N/A"
