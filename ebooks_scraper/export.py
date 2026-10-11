import csv
from collections.abc import Iterable
from pathlib import Path

from .models import Book, CSV_COLUMNS


def write_csv(books: Iterable[Book], output: Path) -> int:
    """Flush each row so completed books survive an interrupted run."""
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        handle.flush()
        for book in books:
            writer.writerow(book.csv_row())
            handle.flush()
            count += 1
    return count
