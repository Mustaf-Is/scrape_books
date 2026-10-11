from dataclasses import asdict, dataclass

MISSING = "N/A"
CSV_COLUMNS = ("url", "title", "price", "published_date", "publisher", "isbns", "authors")


@dataclass(frozen=True)
class Book:
    url: str
    title: str = MISSING
    price: str = MISSING
    published_date: str = MISSING
    publisher: str = MISSING
    isbns: str = MISSING
    authors: str = MISSING

    def csv_row(self) -> dict[str, str]:
        return {key: value.strip() or MISSING for key, value in asdict(self).items()}
