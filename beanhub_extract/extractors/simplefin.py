import csv
import datetime
import decimal
import hashlib
import typing

from ..data_types import Fingerprint
from ..data_types import Transaction
from ..text import as_text
from .base import ExtractorBase


def parse_datetime(dt_str: str) -> tuple[datetime.date, datetime.datetime, str | None]:
    dt = datetime.datetime.fromisoformat(dt_str)
    tz = None
    if dt.tzinfo is not None:
        tz = dt.tzinfo.tzname(dt)
    return dt.date(), dt, tz


class SimpleFinExtractor(ExtractorBase):
    EXTRACTOR_NAME = "simplefin"
    DEFAULT_IMPORT_ID = "{{ file | as_posix_path }}:{{ transaction_id }}"
    ALL_FIELDS = [
        "id",
        "posted",
        "transacted_at",
        "amount",
        "description",
        "pending",
        "currency",
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
                pass
            if row is None:
                return
            hash = hashlib.sha256()
            for field in reader.fieldnames:
                hash.update(row[field].encode("utf8"))
            date, _, _ = parse_datetime(row["transacted_at"])
            return Fingerprint(
                starting_date=date,
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
            for i, row in enumerate(reader):
                transaction_id = row.pop("id")
                posted = row.pop("posted")
                transacted_at = row.pop("transacted_at")
                date, timestamp, timezone = parse_datetime(transacted_at)
                post_date, _, _ = parse_datetime(posted)
                kwargs = dict(
                    transaction_id=transaction_id,
                    date=date,
                    post_date=post_date,
                    timestamp=timestamp,
                    timezone=timezone,
                    amount=decimal.Decimal(row.pop("amount")),
                    desc=row.pop("description"),
                    pending=row.pop("pending").lower() == "true",
                    currency=row.pop("currency"),
                )
                if row:
                    kwargs["extra"] = row

                yield Transaction(
                    extractor=self.EXTRACTOR_NAME,
                    file=filename,
                    lineno=i + 1,
                    reversed_lineno=i - row_count,
                    **kwargs,
                )
