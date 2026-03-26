import contextlib
import csv
import datetime
import decimal
import hashlib
import io
import re
import typing

from ..data_types import Fingerprint, Transaction
from ..text import as_text
from .base import ExtractorBase

DEFAULT_ENCODING = "utf-8-sig"


def parse_date(date_str: str) -> datetime.date:
    """Parse date in MM/DD/YYYY format, handling 'as of' suffix."""
    if not date_str:
        raise ValueError("Empty date string")
    # Handle "01/08/2026 as of 01/07/2026" format - take the first date
    date_str = date_str.split(" as of ")[0].strip()
    parts = date_str.split("/")
    return datetime.date(int(parts[-1]), int(parts[0]), int(parts[1]))


def parse_amount(amount_str: str) -> decimal.Decimal:
    """Parse amount string like '$1,234.56' or '-$1,234.56' to Decimal."""
    if not amount_str or amount_str.strip() == "":
        return decimal.Decimal("0.0")
    # Remove $ sign and commas
    cleaned = amount_str.replace("$", "").replace(",", "").strip()
    try:
        return decimal.Decimal(cleaned)
    except (ValueError, decimal.InvalidOperation):
        return decimal.Decimal("0.0")


def generate_transaction_id(row: dict) -> str:
    """Generate a hash-based transaction ID from key row values."""
    key_fields = [
        row.get("Date", ""),
        row.get("Action", ""),
        row.get("Symbol", ""),
        row.get("Description", ""),
        row.get("Quantity", ""),
        row.get("Price", ""),
        row.get("Amount", ""),
    ]
    combined = "|".join(key_fields)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:32]


class SchwabExtractor(ExtractorBase):
    """Extractor for Charles Schwab brokerage CSV exports."""

    EXTRACTOR_NAME = "schwab"
    DEFAULT_ENCODING = DEFAULT_ENCODING
    DEFAULT_IMPORT_ID = "{{ transaction_id }}"

    def detect(self) -> bool:
        """Detect if this is a Schwab brokerage CSV file."""
        # Reset file position
        self.input_file.seek(0)
        with as_text(self.input_file, encoding=self.DEFAULT_ENCODING) as text_file:
            reader = csv.reader(text_file)
            try:
                header = next(reader)
                # Check for Schwab-specific columns
                expected_cols = {"Date", "Action", "Symbol", "Description", "Quantity", "Price", "Amount"}
                header_set = {col.strip().strip('"') for col in header}
                return expected_cols.issubset(header_set)
            except (StopIteration, csv.Error):
                return False

    def fingerprint(self) -> Fingerprint | None:
        """Generate fingerprint for deduplication."""
        self.input_file.seek(0)
        with as_text(self.input_file, encoding=self.DEFAULT_ENCODING) as text_file:
            reader = csv.DictReader(text_file)
            try:
                first_row = next(reader)
                date_str = first_row.get("Date", "")
                if date_str:
                    # Handle "as of" format
                    date_str = date_str.split(" as of ")[0].strip()
                    parts = date_str.split("/")
                    starting_date = datetime.date(int(parts[-1]), int(parts[0]), int(parts[1]))
                else:
                    return None

                # Create hash of first row
                row_str = "|".join(f"{k}={v}" for k, v in sorted(first_row.items()))
                first_row_hash = hashlib.sha256(row_str.encode("utf-8")).hexdigest()[:16]

                return Fingerprint(starting_date=starting_date, first_row_hash=first_row_hash)
            except (StopIteration, csv.Error, ValueError):
                return None

    def __call__(self) -> typing.Generator[Transaction, None, None]:
        """Extract transactions from Schwab CSV."""
        self.input_file.seek(0)
        filename = getattr(self.input_file, "name", None)
        if filename:
            filename = as_text(filename)

        with as_text(self.input_file, encoding=self.DEFAULT_ENCODING) as text_file:
            reader = csv.DictReader(text_file)

            for row in reader:
                date_str = row.get("Date", "")
                if not date_str:
                    continue

                try:
                    date = parse_date(date_str)
                except (ValueError, IndexError):
                    continue

                # Parse transaction type
                action = row.get("Action", "").strip()
                if not action:
                    continue

                # Parse symbol and description
                symbol = row.get("Symbol", "").strip()
                description = row.get("Description", "").strip()

                # Parse amount
                amount_str = row.get("Amount", "")
                amount = parse_amount(amount_str)

                # Parse quantity and price for trades
                quantity = row.get("Quantity", "").strip()
                price = row.get("Price", "").strip()
                fees_comm = row.get("Fees & Comm", "").strip()

                # Parse fees
                fees = parse_amount(fees_comm) if fees_comm else decimal.Decimal("0.0")

                # Generate hash-based transaction ID
                transaction_id = generate_transaction_id(row)

                # Build extra dict with additional fields
                extra = {
                    "symbol": symbol,
                    "quantity": quantity,
                    "price": price,
                    "fees_comm": str(fees) if fees != 0 else "",
                }

                yield Transaction(
                    extractor=self.EXTRACTOR_NAME,
                    file=filename,
                    transaction_id=transaction_id,
                    date=date,
                    desc=description,
                    bank_desc=description,
                    amount=amount,
                    currency="USD",
                    type=action,
                    extra=extra,
                )
