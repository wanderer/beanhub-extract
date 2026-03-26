import decimal
from decimal import Decimal
from pathlib import Path

import pytest

from beanhub_extract.extractors.schwab import SchwabExtractor


@pytest.fixture
def schwab_csv(fixtures_folder: Path) -> Path:
    return fixtures_folder / "schwab.csv"


class TestSchwabExtractor:
    """Tests for Schwab brokerage CSV extractor."""

    def test_detect(self, schwab_csv: Path) -> None:
        """Test that the extractor correctly identifies Schwab CSV files."""
        with open(schwab_csv, "rb") as f:
            extractor = SchwabExtractor(f)
            assert extractor.detect() is True

    def test_detect_wrong_format(self, fixtures_folder: Path) -> None:
        """Test that extractor returns False for non-Schwab files."""
        wrong_file = fixtures_folder / "mercury.csv"
        with open(wrong_file, "rb") as f:
            extractor = SchwabExtractor(f)
            assert extractor.detect() is False

    def test_fingerprint(self, schwab_csv: Path) -> None:
        """Test fingerprint generation."""
        with open(schwab_csv, "rb") as f:
            extractor = SchwabExtractor(f)
            fingerprint = extractor.fingerprint()
            assert fingerprint is not None
            assert fingerprint.starting_date.year == 2026
            assert fingerprint.starting_date.month == 1
            assert fingerprint.starting_date.day == 2

    def test_extract_dividend(self, schwab_csv: Path) -> None:
        """Test extraction of dividend transaction."""
        with open(schwab_csv, "rb") as f:
            extractor = SchwabExtractor(f)
            transactions = list(extractor())
            # First transaction is the dividend
            txn = transactions[0]
            assert txn.type == "Qualified Dividend"
            assert txn.date.year == 2026
            assert txn.date.month == 1
            assert txn.date.day == 2
            assert txn.amount == Decimal("12.50")
            assert txn.extra.get("symbol") == "AAPL"

    def test_extract_buy(self, schwab_csv: Path) -> None:
        """Test extraction of buy transaction."""
        with open(schwab_csv, "rb") as f:
            extractor = SchwabExtractor(f)
            transactions = list(extractor())
            # Find the buy transaction
            buy_txn = next(t for t in transactions if t.type == "Buy")
            assert buy_txn.date.day == 3
            assert buy_txn.amount == Decimal("-1500.00")
            assert buy_txn.extra.get("symbol") == "AAPL"
            assert buy_txn.extra.get("quantity") == "10"
            assert buy_txn.extra.get("price") == "150.00"

    def test_extract_sell(self, schwab_csv: Path) -> None:
        """Test extraction of sell transaction."""
        with open(schwab_csv, "rb") as f:
            extractor = SchwabExtractor(f)
            transactions = list(extractor())
            # Find the sell transaction
            sell_txn = next(t for t in transactions if t.type == "Sell")
            assert sell_txn.date.day == 5
            assert sell_txn.amount == Decimal("799.50")
            assert sell_txn.extra.get("quantity") == "5"
            assert sell_txn.extra.get("price") == "160.00"
            assert sell_txn.extra.get("fees_comm") == "0.50"

    def test_extract_credit_interest(self, schwab_csv: Path) -> None:
        """Test extraction of credit interest."""
        with open(schwab_csv, "rb") as f:
            extractor = SchwabExtractor(f)
            transactions = list(extractor())
            # Find the credit interest transaction
            interest_txn = next(t for t in transactions if t.type == "Credit Interest")
            assert interest_txn.date.day == 6
            assert interest_txn.amount == Decimal("0.25")

    def test_extract_advisor_fee(self, schwab_csv: Path) -> None:
        """Test extraction of advisor fee."""
        with open(schwab_csv, "rb") as f:
            extractor = SchwabExtractor(f)
            transactions = list(extractor())
            # Find the advisor fee transaction
            fee_txn = next(t for t in transactions if t.type == "Advisor Fee")
            assert fee_txn.date.day == 7
            assert fee_txn.amount == Decimal("-45.00")

    def test_extract_date_with_as_of(self, schwab_csv: Path) -> None:
        """Test extraction of transaction with 'as of' date format."""
        with open(schwab_csv, "rb") as f:
            extractor = SchwabExtractor(f)
            transactions = list(extractor())
            # Find the stock split transaction
            split_txn = next(t for t in transactions if t.type == "Stock Split")
            # Should use the first date (01/08/2026), not the "as of" date
            assert split_txn.date.day == 8

    def test_extract_sell_short(self, schwab_csv: Path) -> None:
        """Test extraction of sell short transaction."""
        with open(schwab_csv, "rb") as f:
            extractor = SchwabExtractor(f)
            transactions = list(extractor())
            # Find the sell short transaction
            short_txn = next(t for t in transactions if t.type == "Sell Short")
            assert short_txn.date.day == 20
            assert short_txn.amount == Decimal("-2500.00")
            assert short_txn.extra.get("symbol") == "GME"

    def test_extract_all_transactions(self, schwab_csv: Path) -> None:
        """Test that all transactions are extracted."""
        with open(schwab_csv, "rb") as f:
            extractor = SchwabExtractor(f)
            transactions = list(extractor())
            assert len(transactions) == 10

    def test_transaction_id_is_hash(self, schwab_csv: Path) -> None:
        """Test that transaction_id is a hash, not file:lineno."""
        with open(schwab_csv, "rb") as f:
            extractor = SchwabExtractor(f)
            transactions = list(extractor())
            for txn in transactions:
                # Should be a 32-char hex string
                assert len(txn.transaction_id) == 32
                # Should be valid hex
                int(txn.transaction_id, 16)

    def test_currency(self, schwab_csv: Path) -> None:
        """Test that currency is USD."""
        with open(schwab_csv, "rb") as f:
            extractor = SchwabExtractor(f)
            transactions = list(extractor())
            for txn in transactions:
                assert txn.currency == "USD"
