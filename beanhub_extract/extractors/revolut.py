import csv
import datetime
import decimal
import hashlib
import typing

import pytz

from ..data_types import Fingerprint
from ..data_types import Transaction
from ..text import as_text
from .base import ExtractorBase


def parse_datetime(timestamp_str: str) -> datetime.datetime:
    return datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")


def parse_date(date_str: str) -> datetime.date:
    return parse_datetime(date_str).date()


class RevolutExtractor(ExtractorBase):
    EXTRACTOR_NAME = "revolut"
    DEFAULT_IMPORT_ID = "{{ file | as_posix_path }}:{{ reversed_lineno }}"
    ALL_FIELDS = [
        "Type",
        "Product",
        "Started Date",
        "Completed Date",
        "Description",
        "Amount",
        "Fee",
        "Currency",
        "State",
        "Balance",
    ]

    def detect(self) -> bool:
        with as_text(self.input_file) as text_file:
            reader = csv.DictReader(text_file)
            try:
                return reader.fieldnames == self.ALL_FIELDS
            except Exception:
                return False

    def fingerprint(self) -> Fingerprint | None:
        with as_text(self.input_file) as text_file:
            reader = csv.DictReader(text_file)
            row = None
            for row in reader:
                if row["State"] != "COMPLETED":
                    continue
                pass
            if row is None:
                return
            hash = hashlib.sha256()
            for field in reader.fieldnames:
                hash.update(row[field].encode("utf8"))
            date_str = row["Completed Date"] or row["Started Date"]
            return Fingerprint(
                starting_date=parse_date(date_str),
                first_row_hash=hash.hexdigest(),
            )

    def __call__(self) -> typing.Generator[Transaction, None, None]:
        filename = None
        if hasattr(self.input_file, "name"):
            filename = self.input_file.name
        with as_text(self.input_file) as text_file:
            rows = list(csv.DictReader(text_file))
            for i, row in enumerate(rows):
                if row["State"] != "COMPLETED":
                    continue
                completed_date_str = row["Completed Date"]
                started_date_str = row["Started Date"]
                fee = decimal.Decimal(row.pop("Fee"))
                txn_type = row.pop("Type")
                amount = decimal.Decimal(row.pop("Amount"))
                if txn_type == "Fee":
                    fee = -amount
                    amount = decimal.Decimal("0")
                if txn_type == "Charge":
                    txn_type = "Fee"
                row["Fee"] = fee
                payee = row.pop("Description")
                date = parse_date(started_date_str)
                row.pop("Product")
                row.pop("Started Date")
                row.pop("Completed Date")
                post_date = None
                if completed_date_str:
                    post_date = parse_date(completed_date_str)
                    if post_date == date:
                        post_date = None
                yield Transaction(
                    extractor=self.EXTRACTOR_NAME,
                    file=filename,
                    lineno=i + 1,
                    reversed_lineno=i - len(rows),
                    timezone="UTC",
                    payee=payee,
                    date=date,
                    post_date=post_date,
                    timestamp=pytz.UTC.localize(parse_datetime(started_date_str)),
                    type=txn_type,
                    desc=txn_type,
                    amount=amount,
                    currency=row.pop("Currency"),
                    status=row.pop("State"),
                    extra=row,
                )
