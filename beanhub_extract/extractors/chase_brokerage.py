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

# Canonical column order for Chase Brokerage CSV exports.
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
ALL_FIELDS_SET = frozenset(ALL_FIELDS)


def parse_date(date_str: str) -> datetime.date:
    """Parse date in M/D/YYYY or MM/DD/YYYY format."""
    parts = date_str.strip().split("/")
    return datetime.date(int(parts[2]), int(parts[0]), int(parts[1]))


def parse_decimal(value: str) -> decimal.Decimal | None:
    """Parse a plain numeric string to Decimal, returning None for blanks."""
    cleaned = value.replace(",", "").strip()
    if not cleaned:
        return None
    try:
        return decimal.Decimal(cleaned)
    except decimal.InvalidOperation:
        return None


def is_valid_row(row: dict) -> bool:
    """A row is valid if Trade Date is a parseable date."""
    raw = row.get("Trade Date", "").strip()
    if not raw:
        return False
    try:
        parse_date(raw)
        return True
    except (ValueError, IndexError):
        return False


def generate_transaction_id(row: dict) -> str:
    """Stable hash derived from the key fields of a row."""
    parts = [
        row.get("Trade Date", ""),
        row.get("Type", ""),
        row.get("Description", ""),
        row.get("Ticker", ""),
        row.get("Quantity", ""),
        row.get("Price USD", ""),
        row.get("Amount USD", ""),
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]


class ChaseBrokerageExtractor(ExtractorBase):
    """Extractor for Chase Brokerage CSV exports.

    The file starts with a BOM (``\\ufeff``) and has 31 columns.
    Dates are in descending order (most recent first).
    """

    EXTRACTOR_NAME = "chase_brokerage"
    DEFAULT_ENCODING = DEFAULT_ENCODING
    DEFAULT_IMPORT_ID = "{{ transaction_id }}"

    def detect(self) -> bool:
        self.input_file.seek(0)
        try:
            with as_text(self.input_file, encoding=self.DEFAULT_ENCODING) as text_file:
                reader = csv.DictReader(text_file)
                if reader.fieldnames is None:
                    return False
                return ALL_FIELDS_SET == frozenset(reader.fieldnames)
        except Exception:
            return False

    def fingerprint(self) -> Fingerprint | None:
        self.input_file.seek(0)
        with as_text(self.input_file, encoding=self.DEFAULT_ENCODING) as text_file:
            reader = csv.DictReader(text_file)
            rows = [r for r in reader if is_valid_row(r)]
            if not rows:
                return None
            # Use last row (oldest date) for a stable fingerprint since the
            # file is in descending date order.
            last = rows[-1]
            h = hashlib.sha256()
            for field in ALL_FIELDS:
                h.update(last.get(field, "").encode())
            return Fingerprint(
                starting_date=parse_date(last["Trade Date"]),
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
                trade_date = parse_date(row["Trade Date"])

                post_date_raw = row.get("Post Date", "").strip()
                try:
                    post_date = parse_date(post_date_raw) if post_date_raw else trade_date
                except (ValueError, IndexError):
                    post_date = trade_date

                txn_type = row.get("Type", "").strip()
                description = row.get("Description", "").strip()
                ticker = row.get("Ticker", "").strip()
                security_type = row.get("Security Type", "").strip()

                amount = parse_decimal(row.get("Amount USD", ""))
                income = parse_decimal(row.get("Income USD", ""))
                commissions = parse_decimal(row.get("Commissions USD", ""))
                price = row.get("Price USD", "").strip()
                quantity = row.get("Quantity", "").replace(",", "").strip()

                account_number = row.get("Account Number", "").strip()
                last_four = account_number[-4:] if len(account_number) >= 4 else account_number

                yield Transaction(
                    extractor=self.EXTRACTOR_NAME,
                    file=filename,
                    lineno=i + 1,
                    reversed_lineno=i - total,
                    transaction_id=generate_transaction_id(row),
                    date=trade_date,
                    post_date=post_date,
                    desc=f"{txn_type} - {description}" if description else txn_type,
                    bank_desc=description,
                    amount=amount,
                    currency="USD",
                    type=txn_type,
                    last_four_digits=last_four,
                    extra={
                        "ticker": ticker,
                        "security_type": security_type,
                        "quantity": quantity,
                        "price": price,
                        "income": str(income) if income else "",
                        "commissions": str(commissions) if commissions else "",
                        "settlement_date": row.get("Settlement Date", "").strip(),
                        "cusip": row.get("Cusip", "").strip(),
                        "local_currency": row.get("Local Currency", "").strip(),
                        "price_local": row.get("Price Local", "").strip(),
                        "amount_local": row.get("Amount Local", "").strip(),
                        "balance": row.get("Balance", "").strip(),
                        "tran_code": row.get("Tran Code", "").strip(),
                        "tran_code_description": row.get("Tran Code Description", "").strip(),
                        "broker": row.get("Broker", "").strip(),
                        "check_number": row.get("Check Number", "").strip(),
                        "tax_withheld": row.get("Tax Withheld", "").strip(),
                        "account_name": row.get("Account Name", "").strip(),
                        "account_type": row.get("Account Type", "").strip(),
                    },
                )
