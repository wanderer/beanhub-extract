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
    date_part, time_part = timestamp_str.split(" ")
    year, month, day = date_part.split("-")
    hour, minute, second = time_part.split(":")
    return datetime.datetime(
        int(year), int(month), int(day), int(hour), int(minute), int(second)
    )


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
            row_count_reader = csv.DictReader(text_file)
            row_count = 0
            for _ in row_count_reader:
                row_count += 1
            text_file.seek(0)
            reader = csv.DictReader(text_file)
            timezone = pytz.UTC
            for i, row in enumerate(reader):
                if row["State"] != "COMPLETED":
                    continue
                completed_date_str = row["Completed Date"]
                started_date_str = row["Started Date"]
                kwargs = dict(
                    date=parse_date(started_date_str),
                    timestamp=timezone.localize(parse_datetime(started_date_str)),
                    type=row.pop("Type"),
                    desc=row.pop("Description"),
                    amount=decimal.Decimal(row.pop("Amount")),
                    currency=row.pop("Currency"),
                    status=row.pop("State"),
                )
                row.pop("Product")
                row.pop("Started Date")
                row.pop("Completed Date")
                if completed_date_str:
                    post_date = parse_date(completed_date_str)
                    if post_date != kwargs["date"]:
                        kwargs["post_date"] = post_date
                if row:
                    kwargs["extra"] = row
                yield Transaction(
                    extractor=self.EXTRACTOR_NAME,
                    file=filename,
                    lineno=i + 1,
                    reversed_lineno=i - row_count,
                    timezone="UTC",
                    **kwargs,
                )
