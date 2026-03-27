import contextlib
import csv
import datetime
import decimal
import hashlib
import re
import typing

from ..data_types import Fingerprint, Transaction
from ..text import as_text
from .base import ExtractorBase

DEFAULT_ENCODING = "utf-8-sig"


def parse_date(date_str: str) -> datetime.date:
    """Parse date in MM/DD/YYYY format."""
    if not date_str:
        raise ValueError("Empty date string")
    parts = date_str.split("/")
    return datetime.date(int(parts[-1]), int(parts[0]), int(parts[1]))


def parse_to_decimal(number_str: str) -> decimal.Decimal:
    """Parse string to Decimal, returning 0 for empty/invalid strings."""
    if not number_str or number_str.strip() == "":
        return decimal.Decimal("0.0")
    try:
        return decimal.Decimal(number_str)
    except (ValueError, decimal.InvalidOperation):
        return decimal.Decimal("0.0")


def skip_leading_empty_lines(input_file: typing.TextIO) -> None:
    """Skip leading empty lines and BOM characters.

    Chase Brokerage CSV files start with a BOM and quoted headers like:
    "Trade Date","Post Date",...
    """
    while True:
        line = input_file.readline()
        if not line:
            break
        stripped = line.lstrip("\ufeff").strip()  # Remove BOM
        if stripped:
            # Found a non-empty line (could be header starting with quote or letter)
            # Rewind to the start of this line
            input_file.seek(input_file.tell() - len(line))
            break


@contextlib.contextmanager
def read_csv(input_file: typing.TextIO | typing.BinaryIO):
    """Context manager to read Chase Brokerage CSV with proper handling."""
    with as_text(input_file, encoding=DEFAULT_ENCODING) as text_file:
        skip_leading_empty_lines(text_file)
        reader = csv.DictReader(
            text_file,
            restkey=None,
            restval=None,
            skipinitialspace=True,
            dialect="excel",
        )
        yield reader


def is_valid_row(row: dict) -> bool:
    """Check if a row is a valid data row (has a date in Trade Date)."""
    date = row.get("Trade Date", "")
    if not date:
        return False
    if re.match(r"^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}$", date):
        try:
            parse_date(date)
            return True
        except ValueError:
            pass
    return False


class ChaseBrokerageExtractor(ExtractorBase):
    """Extractor for Chase Brokerage CSV exports."""

    EXTRACTOR_NAME = "chase_brokerage"
    DEFAULT_ENCODING = DEFAULT_ENCODING
    DEFAULT_IMPORT_ID = "{{ transaction_id }}"

    # All expected CSV columns for Chase Brokerage export
    ALL_FIELDS = [
        "Trade Date",
        "Post Date",
        "Settlement Date",
        "Account Name",
        "Account Number",
        "Account Type",
        "Type",
        "Description",
        "Cusip",
        "Ticker",
        "Security Type",
        "Local Currency",
        "Price USD",
        "Price Local",
        "Quantity",
        "G/L Short USD",
        "G/L Short Local",
        "G/L Long USDs",
        "G/L Long Local",
        "Amount USD",
        "Amount Local",
        "Income USD",
        "Income Local",
        "Balance",
        "Commissions USD",
        "Commissions Local",
        "Tran Code",
        "Tran Code Description",
        "Broker",
        "Check Number",
        "Tax Withheld",
    ]

    def detect(self) -> bool:
        """Detect if this is a Chase Brokerage CSV file."""
        try:
            with read_csv(self.input_file) as reader:
                return reader.fieldnames == self.ALL_FIELDS
        except Exception:
            pass
        return False

    def fingerprint(self) -> Fingerprint | None:
        """Generate fingerprint from the last row (most recent transaction)."""
        with read_csv(self.input_file) as reader:
            valid_rows = list(filter(is_valid_row, reader))
            if not valid_rows:
                return None

            last_row = valid_rows[-1]
            hash_obj = hashlib.sha256()
            for field in self.ALL_FIELDS:
                value = last_row.get(field, "")
                hash_obj.update(value.encode("utf8"))

            try:
                date_value = parse_date(last_row.get("Trade Date", "01/01/1970"))
            except ValueError:
                date_value = datetime.date(1970, 1, 1)

            return Fingerprint(
                starting_date=date_value,
                first_row_hash=hash_obj.hexdigest(),
            )

    def __call__(self) -> typing.Generator[Transaction, None, None]:
        """Extract transactions from Chase Brokerage CSV."""
        filename = None
        if hasattr(self.input_file, "name"):
            filename = self.input_file.name

        # Count rows first
        row_count = 0
        self.input_file.seek(0)
        with read_csv(self.input_file) as reader:
            try:
                for _ in filter(is_valid_row, reader):
                    row_count += 1
            except Exception:
                pass

        self.input_file.seek(0)
        with read_csv(self.input_file) as reader:
            valid_rows = list(filter(is_valid_row, reader))
            for i, row in enumerate(valid_rows):
                trade_date = row.get("Trade Date", "")
                post_date = row.get("Post Date", "")

                # Parse dates
                try:
                    date = parse_date(trade_date) if trade_date else datetime.date(1970, 1, 1)
                except ValueError:
                    date = datetime.date(1970, 1, 1)

                try:
                    post_date_parsed = parse_date(post_date) if post_date else date
                except ValueError:
                    post_date_parsed = date

                # Extract standard fields
                txn_type = row.get("Type", "")
                description = row.get("Description", "")
                ticker = row.get("Ticker", "")
                security_type = row.get("Security Type", "")

                # Amount (Amount USD is the main amount field)
                amount = parse_to_decimal(row.get("Amount USD", "0.0"))

                # Income (for dividends)
                income = parse_to_decimal(row.get("Income USD", "0.0"))

                # Commissions
                commissions = parse_to_decimal(row.get("Commissions USD", "0.0"))

                # Price and quantity for securities
                price = row.get("Price USD", "")
                quantity = row.get("Quantity", "")

                # Settlement date
                settlement_date = row.get("Settlement Date", "")

                # Account number (last 4 digits)
                account_number = row.get("Account Number", "")
                last_four = account_number[-4:] if len(account_number) >= 4 else account_number

                # Build extra dict with all additional fields
                extra = {
                    "ticker": ticker,
                    "security_type": security_type,
                    "quantity": quantity,
                    "price": price,
                    "income": str(income) if income != 0 else "",
                    "commissions": str(commissions) if commissions != 0 else "",
                    "settlement_date": settlement_date,
                    "cusip": row.get("Cusip", ""),
                    "local_currency": row.get("Local Currency", ""),
                    "price_local": row.get("Price Local", ""),
                    "amount_local": row.get("Amount Local", ""),
                    "balance": row.get("Balance", ""),
                    "tran_code": row.get("Tran Code", ""),
                    "tran_code_description": row.get("Tran Code Description", ""),
                    "broker": row.get("Broker", ""),
                    "check_number": row.get("Check Number", ""),
                    "tax_withheld": row.get("Tax Withheld", ""),
                    "account_name": row.get("Account Name", ""),
                    "account_type": row.get("Account Type", ""),
                }

                yield Transaction(
                    extractor=self.EXTRACTOR_NAME,
                    file=filename,
                    lineno=i + 1,
                    reversed_lineno=i - row_count,
                    date=date,
                    post_date=post_date_parsed,
                    desc=description,
                    bank_desc=description,
                    amount=amount,
                    currency="USD",
                    type=txn_type,
                    last_four_digits=last_four,
                    extra=extra,
                )
