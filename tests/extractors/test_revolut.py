import datetime
import decimal
import functools
import pathlib

import pytest
import pytz

from beanhub_extract.data_types import Fingerprint
from beanhub_extract.data_types import Transaction
from beanhub_extract.extractors.revolut import RevolutExtractor
from beanhub_extract.extractors.revolut import parse_date
from beanhub_extract.extractors.revolut import parse_datetime
from beanhub_extract.utils import strip_txn_base_path


@pytest.mark.parametrize(
    "timestamp_str, expected",
    [
        ("2024-04-19 14:25:50", datetime.date(2024, 4, 19)),
    ],
)
def test_parse_date(timestamp_str: str, expected: datetime.date):
    assert parse_date(timestamp_str) == expected


@pytest.mark.parametrize(
    "timestamp_str, expected",
    [
        (
            "2024-04-19 14:25:50",
            datetime.datetime(2024, 4, 19, 14, 25, 50),
        ),
    ],
)
def test_parse_datetime(timestamp_str: str, expected: datetime.datetime):
    assert parse_datetime(timestamp_str) == expected


@pytest.mark.parametrize(
    "input_file, expected",
    [
        (
            "revolut.csv",
            [
                Transaction(
                    extractor="revolut",
                    file="revolut.csv",
                    lineno=1,
                    reversed_lineno=-9,
                    date=datetime.date(2024, 4, 20),
                    timestamp=datetime.datetime(
                        2024, 4, 20, 10, 0, 0, tzinfo=pytz.UTC
                    ),
                    timezone="UTC",
                    type="Deposit",
                    desc="Deposit - Payment from MARTIN BECZE",
                    amount=decimal.Decimal("5000.00"),
                    currency="EUR",
                    status="COMPLETED",
                    extra={"Fee": "0.00", "Balance": "5000.00"},
                ),
                Transaction(
                    extractor="revolut",
                    file="revolut.csv",
                    lineno=2,
                    reversed_lineno=-8,
                    date=datetime.date(2024, 4, 19),
                    post_date=datetime.date(2024, 4, 20),
                    timestamp=datetime.datetime(
                        2024, 4, 19, 14, 25, 50, tzinfo=pytz.UTC
                    ),
                    timezone="UTC",
                    type="Card Payment",
                    desc="Card Payment - eeetwell",
                    amount=decimal.Decimal("-13.00"),
                    currency="EUR",
                    status="COMPLETED",
                    extra={"Fee": "0.00", "Balance": "0.00"},
                ),
                Transaction(
                    extractor="revolut",
                    file="revolut.csv",
                    lineno=3,
                    reversed_lineno=-7,
                    date=datetime.date(2024, 4, 18),
                    timestamp=datetime.datetime(
                        2024, 4, 18, 1, 0, 0, tzinfo=pytz.UTC
                    ),
                    timezone="UTC",
                    type="Transfer",
                    desc="Transfer - To Melita Limited",
                    amount=decimal.Decimal("-39.99"),
                    currency="EUR",
                    status="COMPLETED",
                    extra={"Fee": "0.00", "Balance": "13.00"},
                ),
                Transaction(
                    extractor="revolut",
                    file="revolut.csv",
                    lineno=4,
                    reversed_lineno=-6,
                    date=datetime.date(2024, 4, 17),
                    timestamp=datetime.datetime(
                        2024, 4, 17, 16, 30, 0, tzinfo=pytz.UTC
                    ),
                    timezone="UTC",
                    type="ATM",
                    desc="ATM - Cash withdrawal at ATM",
                    amount=decimal.Decimal("-100.00"),
                    currency="EUR",
                    status="COMPLETED",
                    extra={"Fee": "2.50", "Balance": "52.99"},
                ),
                Transaction(
                    extractor="revolut",
                    file="revolut.csv",
                    lineno=4,
                    reversed_lineno=-6,
                    date=datetime.date(2024, 4, 17),
                    timestamp=datetime.datetime(
                        2024, 4, 17, 16, 30, 0, tzinfo=pytz.UTC
                    ),
                    timezone="UTC",
                    type="Fee",
                    desc="Fee - ATM - Cash withdrawal at ATM",
                    amount=decimal.Decimal("-2.50"),
                    currency="EUR",
                    status="COMPLETED",
                    post_date=None,
                ),
                Transaction(
                    extractor="revolut",
                    file="revolut.csv",
                    lineno=5,
                    reversed_lineno=-5,
                    date=datetime.date(2024, 4, 16),
                    timestamp=datetime.datetime(
                        2024, 4, 16, 9, 0, 0, tzinfo=pytz.UTC
                    ),
                    timezone="UTC",
                    type="Exchange",
                    desc="Exchange - Exchanged to GBP",
                    amount=decimal.Decimal("-50.00"),
                    currency="EUR",
                    status="COMPLETED",
                    extra={"Fee": "0.00", "Balance": "152.99"},
                ),
                Transaction(
                    extractor="revolut",
                    file="revolut.csv",
                    lineno=6,
                    reversed_lineno=-4,
                    date=datetime.date(2024, 4, 15),
                    timestamp=datetime.datetime(
                        2024, 4, 15, 1, 10, 3, tzinfo=pytz.UTC
                    ),
                    timezone="UTC",
                    type="Fee",
                    desc="Fee - Premium plan fee",
                    amount=decimal.Decimal("-7.99"),
                    currency="EUR",
                    status="COMPLETED",
                    extra={"Fee": "0.00", "Balance": "202.99"},
                ),
                Transaction(
                    extractor="revolut",
                    file="revolut.csv",
                    lineno=7,
                    reversed_lineno=-3,
                    date=datetime.date(2024, 4, 14),
                    timestamp=datetime.datetime(
                        2024, 4, 14, 22, 18, 40, tzinfo=pytz.UTC
                    ),
                    timezone="UTC",
                    type="Charge",
                    desc="Charge - Premium plan fee",
                    amount=decimal.Decimal("-8.99"),
                    currency="EUR",
                    status="COMPLETED",
                    extra={"Fee": "8.99", "Balance": "210.98"},
                ),
                Transaction(
                    extractor="revolut",
                    file="revolut.csv",
                    lineno=8,
                    reversed_lineno=-2,
                    date=datetime.date(2024, 4, 13),
                    timestamp=datetime.datetime(
                        2024, 4, 13, 10, 0, 0, tzinfo=pytz.UTC
                    ),
                    timezone="UTC",
                    type="Card Refund",
                    desc="Card Refund - Refund from Amazon",
                    amount=decimal.Decimal("25.50"),
                    currency="EUR",
                    status="COMPLETED",
                    extra={"Fee": "0.00", "Balance": "219.97"},
                ),
            ],
        ),
    ],
)
def test_extractor(
    fixtures_folder: pathlib.Path, input_file: str, expected: list[Transaction]
):
    with open(fixtures_folder / input_file, "rt") as fo:
        extractor = RevolutExtractor(fo)
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
        ("revolut.csv", True),
        ("mercury.csv", False),
        ("chase_credit_card.csv", False),
        ("empty.csv", False),
        ("other.csv", False),
        (pytest.lazy_fixture("zip_file"), False),
    ],
)
def test_detect(fixtures_folder: pathlib.Path, input_file: str, expected: bool):
    with open(fixtures_folder / input_file, "rt") as fo:
        extractor = RevolutExtractor(fo)
        assert extractor.detect() == expected


def test_fingerprint(fixtures_folder: pathlib.Path):
    with open(fixtures_folder / "revolut.csv", "rt") as fo:
        extractor = RevolutExtractor(fo)
        fp = extractor.fingerprint()
        assert fp is not None
        assert fp.starting_date == datetime.date(2024, 4, 12)
