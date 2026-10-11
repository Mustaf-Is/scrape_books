# eBooks.com mathematics scraper

Python scraper using **Playwright's synchronous API** and **visible Chromium** (`channel="chromium", headless=False`). It scrapes pages 1 through `PAGE_COUNT`, opens every unique book URL in a new tab, and exports the results to CSV.

## Setup (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

## Run

```powershell
.\.venv\Scripts\python.exe -m ebooks_scraper
```

The default is **three listing pages**, configured by `PAGE_COUNT = 3` in `ebooks_scraper/config.py`. Page 1 uses the category's base URL (the normal entry point); subsequent pages use `?pageNumber=2` and `?pageNumber=3` in the same session.

Optional overrides:

```powershell
.\.venv\Scripts\python.exe -m ebooks_scraper --pages 3 --output books.csv --timeout-ms 30000 --delay 1
```

CSV columns: `url`, `title`, `price`, `published_date`, `publisher`, `isbns`, `authors`. Multiple ISBNs/authors are separated by `; `. Missing values are `N/A`. Prices retain the site's currency label; dates retain its displayed month/year. UTF-8 with BOM supports Excel, and CSV quoting preserves punctuation and Unicode. Each run replaces the output file.

Completed rows are flushed immediately. Failed book visits are logged and produce a row containing the URL and `N/A` data. Failed listing pages are logged and processing continues with subsequent pages. Any failure results in exit code 1, so check the log before treating a CSV as complete. Browser resources close when processing finishes or is interrupted. The default delay is one second between book visits.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests cover the supplied HTML structure, missing values, multiple ISBNs/authors, duplicate links, CSV quoting and Unicode, and configuration validation. Offline browser tests use visible Chromium with intercepted responses to exercise pagination, delayed JavaScript rendering, fresh book tabs, cleanup, and failed book visits. They require the Chromium installation and an interactive desktop, but no site access.

## Structure and source research

- `config.py`: pagination constants and validated runtime options.
- `parsing.py`: pure HTML parsing, scoped URL collection, and `dt`/`dd` grouping.
- `models.py`: book record and CSV schema.
- `scraper.py`: synchronous browser navigation and rendering waits.
- `export.py`: streaming CSV output.
- `__main__.py`: command-line entry point.

Inspected sources: [mathematics category](https://www.ebooks.com/en-us/category/mathematics/5418/) and [example book](https://www.ebooks.com/en-us/book/211015283/football-analytics-with-python-r/eric-a-eager/). Their static HTML includes unpopulated JavaScript templates, so the scraper waits for populated listing links and product details instead of reading immediately after navigation. Results links are scoped to `ul[aria-label="Search results"] li.searchresult`; metadata comes from `dl.book-details`, grouping every `dd` under its preceding `dt`. Price extraction removes duplicated screen-reader text. The requested page-3 URL could not be retrieved by the web research tool; browser validation is separate from this static inspection.

Debugging on 2026-10-11 identified an initial Cloudflare response with HTTP 403, `cf-mitigated: challenge`, and the title `Just a moment...`. One diagnostic session reached HTTP 200 after verification, while later sessions remained challenged. The scraper now waits for recognized Cloudflare challenges rather than immediately discarding the tab. Successful live scraping is still unverified; these changes do not guarantee site access.

Chromium uses a dedicated persistent profile in `.browser-profile/` to retain any verification cookies across tabs and runs. It is excluded from version control and does not use your personal browser profile. Override its location with `--profile-dir`. Run only one scraper instance per profile directory.

The browser stays visible. Complete any verification prompt in that window within the configured timeout (default 30 seconds). Use `--timeout-ms 120000` if you need more time. Unresolved verification and ordinary HTTP error responses are logged as failures. The scraper does not bypass access challenges. A live site can change selectors or availability independently of the offline tests.
