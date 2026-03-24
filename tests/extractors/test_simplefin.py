import datetime
import decimal
import functools
import pathlib

import pytest

from beanhub_extract.data_types import Fingerprint
from beanhub_extract.data_types import Transaction
from beanhub_extract.extractors.simplefin import SimpleFinExtractor
from beanhub_extract.extractors.simplefin import parse_datetime
from beanhub_extract.utils import strip_txn_base_path


@pytest.mark.parametrize(
    "dt_str, expected_date, expected_tz",
    [
        ("2026-01-13 12:00:00+00:00", datetime.date(2026, 1, 13), "UTC"),
        ("2026-01-13 12:00:00-05:00", datetime.date(2026, 1, 13), "UTC-05:00"),
    ],
)
def test_parse_datetime(dt_str: str, expected_date: datetime.date, expected_tz: str):
    date, timestamp, tz = parse_datetime(dt_str)
    assert date == expected_date
    assert tz == expected_tz


@pytest.mark.parametrize(
    "input_file, expected",
    [
        (
            "simplefin.csv",
            [
                Transaction(
                    extractor="simplefin",
                    file="simplefin.csv",
                    lineno=1,
                    reversed_lineno=-5,
                    transaction_id="TRN-ac184702-8572-445d-9460-a0b9dc5c4dbf",
                    date=datetime.date(2026, 1, 13),
                    post_date=datetime.date(2026, 1, 13),
                    timestamp=datetime.datetime(2026, 1, 13, 12, 0, 0, tzinfo=datetime.timezone.utc),
                    timezone="UTC",
                    amount=decimal.Decimal("-671.00"),
                    desc="GREAT LAKES ENER DRAFT PPD ID: 1296387000",
                    pending=False,
                    currency="USD",
                ),
                Transaction(
                    extractor="simplefin",
                    file="simplefin.csv",
                    lineno=2,
                    reversed_lineno=-4,
                    transaction_id="TRN-2da257eb-29bf-423c-bb9f-81ce53cf3fda",
                    date=datetime.date(2026, 1, 15),
                    post_date=datetime.date(2026, 1, 15),
                    timestamp=datetime.datetime(2026, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc),
                    timezone="UTC",
                    amount=decimal.Decimal("-24320.00"),
                    desc="IRS USATAXPYMT PPD ID: 3387702000",
                    pending=False,
                    currency="USD",
                ),
                Transaction(
                    extractor="simplefin",
                    file="simplefin.csv",
                    lineno=3,
                    reversed_lineno=-3,
                    transaction_id="TRN-dbae486e-6a05-43a0-858f-4f83058250ad",
                    date=datetime.date(2026, 1, 20),
                    post_date=datetime.date(2026, 1, 20),
                    timestamp=datetime.datetime(2026, 1, 20, 12, 0, 0, tzinfo=datetime.timezone.utc),
                    timezone="UTC",
                    amount=decimal.Decimal("471.00"),
                    desc="DEPOSIT ID NUMBER 472324",
                    pending=False,
                    currency="USD",
                ),
                Transaction(
                    extractor="simplefin",
                    file="simplefin.csv",
                    lineno=4,
                    reversed_lineno=-2,
                    transaction_id="TRN-c8d5a356-0262-4fa0-a089-00eef097f555",
                    date=datetime.date(2026, 1, 19),
                    post_date=datetime.date(2026, 1, 20),
                    timestamp=datetime.datetime(2026, 1, 19, 12, 0, 0, tzinfo=datetime.timezone.utc),
                    timezone="UTC",
                    amount=decimal.Decimal("2100.00"),
                    desc="DEPOSIT ID NUMBER 472319",
                    pending=False,
                    currency="USD",
                ),
                Transaction(
                    extractor="simplefin",
                    file="simplefin.csv",
                    lineno=5,
                    reversed_lineno=-1,
                    transaction_id="TRN-2453125c-2485-46c7-838e-d90f39e23808",
                    date=datetime.date(2026, 2, 4),
                    post_date=datetime.date(2026, 2, 4),
                    timestamp=datetime.datetime(2026, 2, 4, 12, 0, 0, tzinfo=datetime.timezone.utc),
                    timezone="UTC",
                    amount=decimal.Decimal("-785.95"),
                    desc="GREAT LAKES ENER",
                    pending=False,
                    currency="USD",
                ),
            ],
        ),
    ],
)
def test_simplefin_extractor(
    fixtures_folder: pathlib.Path, input_file: str, expected: list[Transaction]
):
    with open(fixtures_folder / input_file, "rt") as fo:
        extractor = SimpleFinExtractor(fo)
        assert (
            list(
                map(
                    functools.partial(strip_txn_base_path, fixtures_folder), extractor()
                )
            )
            == expected
        )


@pytest.mark.parametrize(
    "input_file, expected",
    [
        ("simplefin.csv", True),
        ("chase_credit_card.csv", False),
        ("mercury.csv", False),
        ("empty.csv", False),
        ("other.csv", False),
        (pytest.lazy_fixture("zip_file"), False),
    ],
)
def test_simplefin_detect(
    fixtures_folder: pathlib.Path, input_file: str, expected: bool
):
    with open(fixtures_folder / input_file, "rt") as fo:
        extractor = SimpleFinExtractor(fo)
        assert extractor.detect() == expected


def test_simplefin_fingerprint(fixtures_folder: pathlib.Path):
    with open(fixtures_folder / "simplefin.csv", "rt") as fo:
        extractor = SimpleFinExtractor(fo)
        assert extractor.fingerprint() == Fingerprint(
            starting_date=datetime.date(2026, 2, 4),
            first_row_hash="4ce977e747980985468751b8089b6c2b4237e6d9fa52128700846c231e3ccd60",
        )
