import csv

from ebooks_scraper.export import write_csv
from ebooks_scraper.models import Book, CSV_COLUMNS


def test_csv_roundtrip(tmp_path):
    output = tmp_path / "nested" / "books.csv"
    books = [Book(url="https://example.com/1", title='Math, "Logic"\nSecond line', authors="Éva; Bob", price="")]
    assert write_csv(iter(books), output) == 1
    with output.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        assert tuple(reader.fieldnames) == CSV_COLUMNS
        row = next(reader)
        assert row["title"] == books[0].title
        assert row["authors"] == "Éva; Bob"
        assert row["price"] == "N/A"
        assert row["isbns"] == "N/A"


def test_empty_export_still_has_header(tmp_path):
    output = tmp_path / "empty.csv"
    assert write_csv([], output) == 0
    assert output.read_text(encoding="utf-8-sig").strip() == ",".join(CSV_COLUMNS)
