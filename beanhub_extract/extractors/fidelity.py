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
DATE_FIELD = "Run Date"


def beanify_account(name: str) -> str:
    rst = re.sub(r"[^a-zA-Z0-9-_ ]", "", name)
    rst = re.sub(r"[ \t\n\r\v\f]", " ", rst)
    rst = re.sub(r"[ ]{2,}", " ", rst)
    rst = rst.replace(" ", "-")
    return rst.title()


def parse_date(date_str: str) -> datetime.date:
    parts = date_str.split("/")
    return datetime.date(int(parts[-1]), *(map(int, parts[:-1])))


def parse_to_decimal(number_str: str) -> decimal.Decimal:
    try:
        return decimal.Decimal(number_str)
    except (ValueError, decimal.InvalidOperation):
        pass

    return decimal.Decimal("0.0")


def skip_leading_empty_lines(input_file: typing.TextIO):
    while True:
        line = input_file.readline().strip()
        if not line:
            # empty line, skip
            continue
        # rewind to start of that line
        input_file.seek(input_file.tell() - len(line) - 1)

        break


@contextlib.contextmanager
def read_cvs(input_file: typing.TextIO | typing.BinaryIO):
    with as_text(
        input_file, encoding=DEFAULT_ENCODING
    ) as text_file:  # type: typing.TextIO
        # Skip BOM and leading empty lines until we find the first 'R'
        while True:
            line = text_file.readline()
            if not line:
                break
            stripped = line.lstrip("\ufeff").strip()  # Remove BOM character
            if (
                stripped and stripped[0] == "R"
            ):  # "Run Date" maks beginning of valid header
                # Found the header line starting with 'R', rewind
                text_file.seek(text_file.tell() - len(line))
                break

        reader = csv.DictReader(
            text_file,
            restkey=None,
            restval=None,
            skipinitialspace=True,
            dialect="excel",
        )
        yield reader


def is_valid_row(row: dict) -> bool:
    date = row.get(DATE_FIELD, "")
    if date is None:
        return False
    if re.match(r"^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}$", date):
        try:
            _ = parse_date(date)
            return True
        except ValueError:
            pass
    return False


class FidelityExtractor(ExtractorBase):
    """Extractor for Fidelity CSV exports"""

    EXTRACTOR_NAME = "fidelity"
    DEFAULT_ENCODING = DEFAULT_ENCODING
    DEFAULT_IMPORT_ID = "{{ file | as_posix_path }}:{{ reversed_lineno }}"
    DATE_FIELD = DATE_FIELD
    ALL_FIELDS = [
        DATE_FIELD,
        "Account",
        "Account Number",
        "Action",
        "Symbol",
        "Description",
        "Type",
        "Exchange Quantity",
        "Exchange Currency",
        "Currency",
        "Price",
        "Quantity",
        "Exchange Rate",
        "Commission",
        "Fees",
        "Accrued Interest",
        "Amount",
        "Settlement Date",
    ]

    def detect(self) -> bool:
        try:
            with read_cvs(self.input_file) as reader:
                return reader.fieldnames == self.ALL_FIELDS
        except Exception:
            pass

        return False

    def fingerprint(self) -> Fingerprint | None:
        with read_cvs(self.input_file) as reader:
            # get first row
            it = filter(is_valid_row, reader)
            try:
                row = next(it)
            except StopIteration:
                return None

            hash = hashlib.sha256()
            for field in reader.fieldnames:
                hash.update(row[field].encode("utf8"))

            date_value = parse_date(row["Run Date"])
            if not date_value:
                date_value = datetime.date(1970, 1, 1)
            return Fingerprint(
                starting_date=date_value,
                first_row_hash=hash.hexdigest(),
            )

    def __call__(self) -> typing.Generator[Transaction, None, None]:
        filename = None
        if hasattr(self.input_file, "name"):
            filename = self.input_file.name

        row_count = 0
        self.input_file.seek(0)
        with read_cvs(self.input_file) as reader:
            it = filter(is_valid_row, reader)
            try:
                for _ in it:
                    row_count += 1
            except Exception:
                pass

        self.input_file.seek(0)
        with read_cvs(self.input_file) as reader:
            it = filter(is_valid_row, reader)
            for i, row in enumerate(it):
                run_date = parse_date(row.get("Run Date", "01/01/1970"))

                # account
                source_account = beanify_account(row.get("Account", ""))

                # description of the transaction
                desc = row.get("Action", "")

                # date of the transaction
                date = run_date

                # date when the transaction posted
                post_date = run_date

                # description of the transaction provided by the bank
                bank_desc = row.get("Description", "")

                # ISO 4217 currency symbol
                currency = row.get("Currency", "")

                # status of the transaction
                t_type = row.get("Type", "")

                # transaction amount
                amount = parse_to_decimal(row.get("Amount", "0.0"))

                last_four_digits = row.get("Account Number", "")[-4:]

                yield Transaction(
                    extractor=self.EXTRACTOR_NAME,
                    file=filename,
                    lineno=i + 1,
                    reversed_lineno=i - row_count,
                    source_account=source_account,
                    date=date,
                    post_date=post_date,
                    desc=desc,
                    bank_desc=bank_desc,
                    amount=amount,
                    currency=currency,
                    type=t_type,
                    last_four_digits=last_four_digits,
                    extra=row,
                )
