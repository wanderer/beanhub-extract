import decimal
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
        """Test that the extractor correctly identifies Chase Brokerage CSV files."""
        with open(chase_brokerage_csv, "rb") as f:
            extractor = ChaseBrokerageExtractor(f)
            assert extractor.detect() is True

    def test_detect_wrong_format(self, fixtures_folder: Path) -> None:
        """Test that extractor returns False for non-Chase Brokerage files."""
        wrong_file = fixtures_folder / "mercury.csv"
        with open(wrong_file, "rb") as f:
            extractor = ChaseBrokerageExtractor(f)
            assert extractor.detect() is False

    def test_fingerprint(self, chase_brokerage_csv: Path) -> None:
        """Test fingerprint generation."""
        with open(chase_brokerage_csv, "rb") as f:
            extractor = ChaseBrokerageExtractor(f)
            fingerprint = extractor.fingerprint()
            assert fingerprint is not None
            assert fingerprint.starting_date.year == 2026
            assert fingerprint.starting_date.month == 3
            assert fingerprint.starting_date.day == 13

    def test_extract_deposit_sweep(self, chase_brokerage_csv: Path) -> None:
        """Test extracting a DBS (Deposit Sweep) transaction."""
        with open(chase_brokerage_csv, "rb") as f:
            extractor = ChaseBrokerageExtractor(f)
            txns = list(extractor())

            # Find DBS transaction
            dbs_txn = None
            for txn in txns:
                if txn.type == "DBS":
                    dbs_txn = txn
                    break

            assert dbs_txn is not None
            assert dbs_txn.date.year == 2026
            assert dbs_txn.date.month == 3
            assert dbs_txn.date.day == 17
            assert dbs_txn.amount == Decimal("-0.01")
            assert "INTRA-DAY DEPOSIT" in dbs_txn.desc

    def test_extract_interest(self, chase_brokerage_csv: Path) -> None:
        """Test extracting an Interest transaction."""
        with open(chase_brokerage_csv, "rb") as f:
            extractor = ChaseBrokerageExtractor(f)
            txns = list(extractor())

            # Find Interest transaction
            interest_txn = None
            for txn in txns:
                if txn.type == "Interest":
                    interest_txn = txn
                    break

            assert interest_txn is not None
            assert interest_txn.amount == Decimal("0.01")
            assert "ACCRUED INT" in interest_txn.desc

    def test_extract_withdrawal(self, chase_brokerage_csv: Path) -> None:
        """Test extracting a WDL (Withdrawal) transaction."""
        with open(chase_brokerage_csv, "rb") as f:
            extractor = ChaseBrokerageExtractor(f)
            txns = list(extractor())

            # Find WDL transaction
            wdl_txn = None
            for txn in txns:
                if txn.type == "WDL":
                    wdl_txn = txn
                    break

            assert wdl_txn is not None
            assert wdl_txn.amount == Decimal("11000")
            assert "INTRA-DAY WITHDRWAL" in wdl_txn.desc

    def test_extract_ach_transfer(self, chase_brokerage_csv: Path) -> None:
        """Test extracting a BNK (ACH) transaction."""
        with open(chase_brokerage_csv, "rb") as f:
            extractor = ChaseBrokerageExtractor(f)
            txns = list(extractor())

            # Find BNK transaction
            bnk_txn = None
            for txn in txns:
                if txn.type == "BNK":
                    bnk_txn = txn
                    break

            assert bnk_txn is not None
            assert bnk_txn.amount == Decimal("1000")
            assert "BANKLINK ACH PULL" in bnk_txn.desc

    def test_extract_buy_mutual_fund(self, chase_brokerage_csv: Path) -> None:
        """Test extracting a Buy transaction for a mutual fund."""
        with open(chase_brokerage_csv, "rb") as f:
            extractor = ChaseBrokerageExtractor(f)
            txns = list(extractor())

            # Find Buy transaction for ARTZX
            buy_txn = None
            for txn in txns:
                if txn.type == "Buy" and txn.extra and txn.extra.get("ticker") == "ARTZX":
                    buy_txn = txn
                    break

            assert buy_txn is not None
            assert buy_txn.amount == Decimal("-5000")
            assert buy_txn.extra["ticker"] == "ARTZX"
            assert buy_txn.extra["quantity"] == "202.102"
            assert buy_txn.extra["price"] == "24.74"
            assert buy_txn.extra["security_type"] == "Mutual Fund"

    def test_extract_buy_stock(self, chase_brokerage_csv: Path) -> None:
        """Test extracting a Buy transaction for a stock."""
        with open(chase_brokerage_csv, "rb") as f:
            extractor = ChaseBrokerageExtractor(f)
            txns = list(extractor())

            # Find Buy transaction for AIRR
            buy_txn = None
            for txn in txns:
                if txn.type == "Buy" and txn.extra and txn.extra.get("ticker") == "AIRR":
                    buy_txn = txn
                    break

            assert buy_txn is not None
            assert buy_txn.extra["ticker"] == "AIRR"
            assert buy_txn.extra["security_type"] == "Stock"

    def test_extract_all_transactions(self, chase_brokerage_csv: Path) -> None:
        """Test that all transactions are extracted."""
        with open(chase_brokerage_csv, "rb") as f:
            extractor = ChaseBrokerageExtractor(f)
            txns = list(extractor())

            # Should have 9 transactions in the test file
            assert len(txns) == 9

            # Check transaction types
            types = [txn.type for txn in txns]
            assert types.count("DBS") == 2  # Two deposits
            assert types.count("WDL") == 1  # One withdrawal
            assert types.count("BNK") == 2  # Two ACH transfers
            assert types.count("Interest") == 1  # One interest
            assert types.count("Buy") == 3  # Three buys

    def test_reversed_lineno(self, chase_brokerage_csv: Path) -> None:
        """Test that reversed_lineno is correctly calculated."""
        with open(chase_brokerage_csv, "rb") as f:
            extractor = ChaseBrokerageExtractor(f)
            txns = list(extractor())

            # reversed_lineno = i - row_count
            # For 9 transactions (row_count=9):
            # - First (i=0): 0 - 9 = -9
            # - Last (i=8): 8 - 9 = -1
            assert txns[0].reversed_lineno == -9
            assert txns[-1].reversed_lineno == -1

    def test_last_four_digits(self, chase_brokerage_csv: Path) -> None:
        """Test that last four digits are extracted correctly."""
        with open(chase_brokerage_csv, "rb") as f:
            extractor = ChaseBrokerageExtractor(f)
            txns = list(extractor())

            # Account number is "...6946"
            for txn in txns:
                assert txn.last_four_digits == "6946"

    def test_currency(self, chase_brokerage_csv: Path) -> None:
        """Test that currency is set to USD."""
        with open(chase_brokerage_csv, "rb") as f:
            extractor = ChaseBrokerageExtractor(f)
            txns = list(extractor())

            for txn in txns:
                assert txn.currency == "USD"

    def test_extra_fields(self, chase_brokerage_csv: Path) -> None:
        """Test that extra fields are populated."""
        with open(chase_brokerage_csv, "rb") as f:
            extractor = ChaseBrokerageExtractor(f)
            txns = list(extractor())

            # Find a Buy transaction
            buy_txn = None
            for txn in txns:
                if txn.type == "Buy":
                    buy_txn = txn
                    break

            assert buy_txn is not None
            assert buy_txn.extra is not None
            assert "cusip" in buy_txn.extra
            assert "settlement_date" in buy_txn.extra
            assert "commissions" in buy_txn.extra
