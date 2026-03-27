from decimal import Decimal
from pathlib import Path

import pytest

from beanhub_extract.extractors.chase_brokerage import ChaseBrokerageExtractor


@pytest.fixture
def chase_brokerage_csv(fixtures_folder: Path) -> Path:
    return fixtures_folder / "chase_brokerage.csv"


class TestChaseBrokerageExtractor:
    """Tests for Chase Brokerage CSV extractor."""

    def test_detect(self, chase_brokerage_csv: Path) -> None:
        with open(chase_brokerage_csv, "rb") as f:
            assert ChaseBrokerageExtractor(f).detect() is True

    def test_detect_wrong_format(self, fixtures_folder: Path) -> None:
        with open(fixtures_folder / "mercury.csv", "rb") as f:
            assert ChaseBrokerageExtractor(f).detect() is False

    def test_fingerprint(self, chase_brokerage_csv: Path) -> None:
        with open(chase_brokerage_csv, "rb") as f:
            fp = ChaseBrokerageExtractor(f).fingerprint()
            assert fp is not None
            assert fp.starting_date.year == 2026
            assert fp.starting_date.month == 3
            assert fp.starting_date.day == 13
            assert isinstance(fp.first_row_hash, str)
            assert len(fp.first_row_hash) > 0

    def test_extract_all_transactions(self, chase_brokerage_csv: Path) -> None:
        with open(chase_brokerage_csv, "rb") as f:
            txns = list(ChaseBrokerageExtractor(f)())
            assert len(txns) == 9

            types = [t.type for t in txns]
            assert types.count("DBS") == 2
            assert types.count("WDL") == 1
            assert types.count("BNK") == 2
            assert types.count("Interest") == 1
            assert types.count("Buy") == 3

    def test_currency(self, chase_brokerage_csv: Path) -> None:
        with open(chase_brokerage_csv, "rb") as f:
            for txn in ChaseBrokerageExtractor(f)():
                assert txn.currency == "USD"

    def test_transaction_id_populated(self, chase_brokerage_csv: Path) -> None:
        """Every transaction must have a non-empty transaction_id."""
        with open(chase_brokerage_csv, "rb") as f:
            for txn in ChaseBrokerageExtractor(f)():
                assert txn.transaction_id is not None
                assert len(txn.transaction_id) == 32

    def test_reversed_lineno(self, chase_brokerage_csv: Path) -> None:
        with open(chase_brokerage_csv, "rb") as f:
            txns = list(ChaseBrokerageExtractor(f)())
            assert txns[0].lineno == 1
            assert txns[0].reversed_lineno == -9
            assert txns[-1].lineno == 9
            assert txns[-1].reversed_lineno == -1

    def test_last_four_digits(self, chase_brokerage_csv: Path) -> None:
        with open(chase_brokerage_csv, "rb") as f:
            for txn in ChaseBrokerageExtractor(f)():
                assert txn.last_four_digits == "6946"

    # -- Specific transaction types --

    def test_extract_deposit_sweep(self, chase_brokerage_csv: Path) -> None:
        with open(chase_brokerage_csv, "rb") as f:
            txn = next(t for t in ChaseBrokerageExtractor(f)() if t.type == "DBS")
            assert txn.date.year == 2026
            assert txn.date.month == 3
            assert txn.date.day == 17
            assert txn.amount == Decimal("-0.01")
            assert "INTRA-DAY DEPOSIT" in txn.desc

    def test_extract_interest(self, chase_brokerage_csv: Path) -> None:
        with open(chase_brokerage_csv, "rb") as f:
            txn = next(t for t in ChaseBrokerageExtractor(f)() if t.type == "Interest")
            assert txn.amount == Decimal("0.01")
            assert "ACCRUED INT" in txn.desc

    def test_extract_withdrawal(self, chase_brokerage_csv: Path) -> None:
        with open(chase_brokerage_csv, "rb") as f:
            txn = next(t for t in ChaseBrokerageExtractor(f)() if t.type == "WDL")
            assert txn.amount == Decimal("11000")
            assert "INTRA-DAY WITHDRWAL" in txn.desc

    def test_extract_ach_transfer(self, chase_brokerage_csv: Path) -> None:
        with open(chase_brokerage_csv, "rb") as f:
            txn = next(t for t in ChaseBrokerageExtractor(f)() if t.type == "BNK")
            assert txn.amount == Decimal("1000")
            assert "BANKLINK ACH PULL" in txn.desc

    def test_extract_buy_mutual_fund(self, chase_brokerage_csv: Path) -> None:
        with open(chase_brokerage_csv, "rb") as f:
            txn = next(
                t
                for t in ChaseBrokerageExtractor(f)()
                if t.type == "Buy" and t.extra.get("ticker") == "ARTZX"
            )
            assert txn.amount == Decimal("-5000")
            assert txn.extra["quantity"] == "202.102"
            assert txn.extra["price"] == "24.74"
            assert txn.extra["security_type"] == "Mutual Fund"

    def test_extract_buy_stock(self, chase_brokerage_csv: Path) -> None:
        with open(chase_brokerage_csv, "rb") as f:
            txn = next(
                t
                for t in ChaseBrokerageExtractor(f)()
                if t.type == "Buy" and t.extra.get("ticker") == "AIRR"
            )
            assert txn.extra["security_type"] == "Stock"

    def test_extra_fields(self, chase_brokerage_csv: Path) -> None:
        with open(chase_brokerage_csv, "rb") as f:
            txn = next(t for t in ChaseBrokerageExtractor(f)() if t.type == "Buy")
            assert txn.extra is not None
            assert "cusip" in txn.extra
            assert "settlement_date" in txn.extra
            assert "commissions" in txn.extra
