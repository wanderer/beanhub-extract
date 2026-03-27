import csv
import datetime
import decimal
import hashlib
import typing

from ..data_types import Fingerprint, Transaction
from ..text import as_text
from .base import ExtractorBase

DEFAULT_ENCODING = "utf-8-sig"


def parse_date(date_str: str) -> datetime.date:
    """Parse date in MM/DD/YYYY format, handling 'as of' suffix."""
    if not date_str:
        raise ValueError("Empty date string")
    date_str = date_str.split(" as of ")[0].strip()
    parts = date_str.split("/")
    return datetime.date(int(parts[-1]), int(parts[0]), int(parts[1]))


def parse_amount(amount_str: str) -> decimal.Decimal:
    """Parse amount string like '$1,234.56' or '-$1,234.56' to Decimal."""
    if not amount_str or amount_str.strip() == "":
        return decimal.Decimal("0.0")
    cleaned = amount_str.replace("$", "").replace(",", "").strip()
    try:
        return decimal.Decimal(cleaned)
    except (ValueError, decimal.InvalidOperation):
        return decimal.Decimal("0.0")


def is_valid_row(row: dict) -> bool:
    """Check if a row is a valid data row."""
    date_str = row.get("Date", "")
    if not date_str:
        return False
    try:
        parse_date(date_str)
    except (ValueError, IndexError):
        return False
    action = row.get("Action", "").strip()
    if not action:
        return False
    return True


class SchwabExtractor(ExtractorBase):
    """Extractor for Charles Schwab brokerage CSV exports."""

    EXTRACTOR_NAME = "schwab"
    DEFAULT_ENCODING = DEFAULT_ENCODING
    DEFAULT_IMPORT_ID = "{{ transaction_id }}"

    def detect(self) -> bool:
        """Detect if this is a Schwab brokerage CSV file."""
        self.input_file.seek(0)
        try:
            with as_text(self.input_file, encoding=self.DEFAULT_ENCODING) as text_file:
                reader = csv.reader(text_file)
                header = next(reader)
                expected_cols = {"Date", "Action", "Symbol", "Description", "Quantity", "Price", "Amount"}
                header_set = {col.strip().strip('"') for col in header}
                return expected_cols.issubset(header_set)
        except (StopIteration, csv.Error, UnicodeDecodeError):
            return False
        except Exception:
            return False

    def fingerprint(self) -> Fingerprint | None:
        """Generate fingerprint for deduplication."""
        self.input_file.seek(0)
        with as_text(self.input_file, encoding=self.DEFAULT_ENCODING) as text_file:
            reader = csv.DictReader(text_file)
            valid_rows = list(filter(is_valid_row, reader))
            try:
                first_row = valid_rows[0]
            except IndexError:
                return None

            try:
                starting_date = parse_date(first_row["Date"])
            except (ValueError, IndexError):
                return None

            hash_obj = hashlib.sha256()
            for field in reader.fieldnames:
                hash_obj.update(first_row[field].encode("utf8"))

            return Fingerprint(
                starting_date=starting_date,
                first_row_hash=hash_obj.hexdigest(),
            )

    def __call__(self) -> typing.Generator[Transaction, None, None]:
        """Extract transactions from Schwab CSV."""
        self.input_file.seek(0)
        filename = getattr(self.input_file, "name", None)
        if filename and not isinstance(filename, str):
            filename = str(filename)

        with as_text(self.input_file, encoding=self.DEFAULT_ENCODING) as text_file:
            reader = csv.DictReader(text_file)
            valid_rows = list(filter(is_valid_row, reader))
            row_count = len(valid_rows)

            for i, row in enumerate(valid_rows):
                date = parse_date(row["Date"])
                action = row.get("Action", "").strip()
                symbol = row.get("Symbol", "").strip()
                description = row.get("Description", "").strip()
                amount = parse_amount(row.get("Amount", ""))
                quantity = row.get("Quantity", "").strip()
                price = row.get("Price", "").strip().replace("$", "")
                fees = parse_amount(row.get("Fees & Comm", ""))

                extra = {
                    "symbol": symbol,
                    "quantity": quantity,
                    "price": price,
                    "fees_comm": str(fees) if fees != 0 else "",
                }

                yield Transaction(
                    extractor=self.EXTRACTOR_NAME,
                    file=filename,
                    lineno=i + 1,
                    reversed_lineno=i - row_count,
                    date=date,
                    desc=f"{action} - {description}",
                    bank_desc=description,
                    amount=amount,
                    currency="USD",
                    type=action,
                    extra=extra,
                )
