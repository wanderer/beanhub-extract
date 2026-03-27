import csv
import datetime
import decimal
import hashlib
import typing

from ..data_types import Fingerprint
from ..data_types import Transaction
from ..text import as_text
from .base import ExtractorBase

DEFAULT_ENCODING = "utf-8-sig"
EXPECTED_COLUMNS = frozenset(
    {"Date", "Action", "Symbol", "Description", "Quantity", "Price", "Fees & Comm", "Amount"}
)


def parse_date(date_str: str) -> datetime.date:
    """Parse date in MM/DD/YYYY format, ignoring any 'as of' suffix."""
    date_str = date_str.split(" as of ")[0].strip()
    parts = date_str.split("/")
    return datetime.date(int(parts[2]), int(parts[0]), int(parts[1]))


def parse_amount(amount_str: str) -> decimal.Decimal | None:
    """Parse dollar amount like '$1,234.56' or '-$1,234.56'.

    Returns None for empty/blank strings.
    """
    cleaned = amount_str.replace("$", "").replace(",", "").strip()
    if not cleaned:
        return None
    return decimal.Decimal(cleaned)


def parse_quantity(quantity_str: str) -> str:
    """Clean quantity string by removing commas."""
    return quantity_str.replace(",", "").strip()


def is_valid_row(row: dict) -> bool:
    """A row is valid if it has a parseable date and a non-empty action."""
    date_str = row.get("Date", "").strip()
    if not date_str:
        return False
    try:
        parse_date(date_str)
    except (ValueError, IndexError):
        return False
    return bool(row.get("Action", "").strip())


def generate_transaction_id(row: dict) -> str:
    """Stable hash from the key fields of a row."""
    parts = [
        row.get("Date", ""),
        row.get("Action", ""),
        row.get("Symbol", ""),
        row.get("Description", ""),
        row.get("Quantity", ""),
        row.get("Price", ""),
        row.get("Amount", ""),
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]


class SchwabExtractor(ExtractorBase):
    """Extractor for Charles Schwab brokerage CSV exports.

    CSV format (all fields quoted):
        Date,Action,Symbol,Description,Quantity,Price,Fees & Comm,Amount

    * Dates are MM/DD/YYYY, optionally with an " as of MM/DD/YYYY" suffix.
    * Dollar values are prefixed with ``$`` and use commas for thousands.
    * Quantity may also contain commas.
    """

    EXTRACTOR_NAME = "schwab"
    DEFAULT_ENCODING = DEFAULT_ENCODING
    DEFAULT_IMPORT_ID = "{{ transaction_id }}"

    def detect(self) -> bool:
        self.input_file.seek(0)
        try:
            with as_text(self.input_file, encoding=self.DEFAULT_ENCODING) as text_file:
                header = next(csv.reader(text_file))
                return EXPECTED_COLUMNS.issubset(
                    col.strip().strip('"') for col in header
                )
        except Exception:
            return False

    def fingerprint(self) -> Fingerprint | None:
        self.input_file.seek(0)
        with as_text(self.input_file, encoding=self.DEFAULT_ENCODING) as text_file:
            reader = csv.DictReader(text_file)
            rows = [r for r in reader if is_valid_row(r)]
            if not rows:
                return None
            first = rows[0]
            h = hashlib.sha256()
            for field in reader.fieldnames:
                h.update(first.get(field, "").encode())
            return Fingerprint(
                starting_date=parse_date(first["Date"]),
                first_row_hash=h.hexdigest(),
            )

    def __call__(self) -> typing.Generator[Transaction, None, None]:
        self.input_file.seek(0)
        filename = getattr(self.input_file, "name", None)
        if filename is not None and not isinstance(filename, str):
            filename = str(filename)

        with as_text(self.input_file, encoding=self.DEFAULT_ENCODING) as text_file:
            reader = csv.DictReader(text_file)
            rows = [r for r in reader if is_valid_row(r)]
            total = len(rows)

            for i, row in enumerate(rows):
                date = parse_date(row["Date"])
                action = row.get("Action", "").strip()
                symbol = row.get("Symbol", "").strip()
                description = row.get("Description", "").strip()
                amount = parse_amount(row.get("Amount", ""))
                quantity = parse_quantity(row.get("Quantity", ""))
                price_raw = row.get("Price", "").replace("$", "").replace(",", "").strip()
                fees = parse_amount(row.get("Fees & Comm", ""))

                yield Transaction(
                    extractor=self.EXTRACTOR_NAME,
                    file=filename,
                    lineno=i + 1,
                    reversed_lineno=i - total,
                    transaction_id=generate_transaction_id(row),
                    date=date,
                    desc=f"{action} - {description}" if description else action,
                    bank_desc=description,
                    amount=amount,
                    currency="USD",
                    type=action,
                    extra={
                        "symbol": symbol,
                        "quantity": quantity,
                        "price": price_raw,
                        "fees_comm": str(fees) if fees else "",
                    },
                )
