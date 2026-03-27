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
        with open(schwab_csv, "rb") as f:
            assert SchwabExtractor(f).detect() is True

    def test_detect_wrong_format(self, fixtures_folder: Path) -> None:
        with open(fixtures_folder / "mercury.csv", "rb") as f:
            assert SchwabExtractor(f).detect() is False

    def test_fingerprint(self, schwab_csv: Path) -> None:
        with open(schwab_csv, "rb") as f:
            fp = SchwabExtractor(f).fingerprint()
            assert fp is not None
            assert fp.starting_date.year == 2026
            assert fp.starting_date.month == 1
            assert fp.starting_date.day == 2
            assert isinstance(fp.first_row_hash, str)
            assert len(fp.first_row_hash) > 0

    def test_extract_all_transactions(self, schwab_csv: Path) -> None:
        with open(schwab_csv, "rb") as f:
            txns = list(SchwabExtractor(f)())
            assert len(txns) == 10

    def test_currency(self, schwab_csv: Path) -> None:
        with open(schwab_csv, "rb") as f:
            for txn in SchwabExtractor(f)():
                assert txn.currency == "USD"

    def test_transaction_id_populated(self, schwab_csv: Path) -> None:
        """Every transaction must have a non-empty transaction_id."""
        with open(schwab_csv, "rb") as f:
            for txn in SchwabExtractor(f)():
                assert txn.transaction_id is not None
                assert len(txn.transaction_id) == 32

    def test_transaction_ids_unique(self, schwab_csv: Path) -> None:
        """All transaction IDs should be distinct (given our fixture has no exact duplicate rows)."""
        with open(schwab_csv, "rb") as f:
            ids = [txn.transaction_id for txn in SchwabExtractor(f)()]
            # The two Journal rows have different quantities (+50 / -50) so
            # their IDs should differ.
            assert len(ids) == len(set(ids))

    def test_lineno_and_reversed_lineno(self, schwab_csv: Path) -> None:
        with open(schwab_csv, "rb") as f:
            txns = list(SchwabExtractor(f)())
            assert txns[0].lineno == 1
            assert txns[0].reversed_lineno == -10
            assert txns[-1].lineno == 10
            assert txns[-1].reversed_lineno == -1

    # -- Dividend --

    def test_extract_dividend(self, schwab_csv: Path) -> None:
        with open(schwab_csv, "rb") as f:
            txn = list(SchwabExtractor(f)())[0]
            assert txn.type == "Qualified Dividend"
            assert txn.date.year == 2026
            assert txn.date.month == 1
            assert txn.date.day == 2
            assert txn.amount == Decimal("12.50")
            assert txn.extra["symbol"] == "AAPL"
            # desc should be just the description, NOT "Qualified Dividend - APPLE INC"
            assert txn.desc == "APPLE INC"

    # -- Buy --

    def test_extract_buy(self, schwab_csv: Path) -> None:
        with open(schwab_csv, "rb") as f:
            buy = next(t for t in SchwabExtractor(f)() if t.type == "Buy")
            assert buy.date.day == 3
            assert buy.amount == Decimal("-1500.00")
            assert buy.extra["symbol"] == "AAPL"
            assert buy.extra["quantity"] == "10"
            assert buy.extra["price"] == "150.00"
            assert buy.desc == "APPLE INC"

    # -- Sell --

    def test_extract_sell(self, schwab_csv: Path) -> None:
        with open(schwab_csv, "rb") as f:
            sell = next(t for t in SchwabExtractor(f)() if t.type == "Sell")
            assert sell.date.day == 5
            assert sell.amount == Decimal("799.50")
            assert sell.extra["quantity"] == "5"
            assert sell.extra["price"] == "160.00"
            assert sell.extra["fees_comm"] == "0.50"

    # -- Credit Interest --

    def test_extract_credit_interest(self, schwab_csv: Path) -> None:
        with open(schwab_csv, "rb") as f:
            txn = next(t for t in SchwabExtractor(f)() if t.type == "Credit Interest")
            assert txn.date.day == 6
            assert txn.amount == Decimal("0.25")

    # -- Advisor Fee --

    def test_extract_advisor_fee(self, schwab_csv: Path) -> None:
        with open(schwab_csv, "rb") as f:
            txn = next(t for t in SchwabExtractor(f)() if t.type == "Advisor Fee")
            assert txn.date.day == 7
            assert txn.amount == Decimal("-45.00")

    # -- "as of" date handling --

    def test_extract_date_with_as_of(self, schwab_csv: Path) -> None:
        with open(schwab_csv, "rb") as f:
            txn = next(t for t in SchwabExtractor(f)() if t.type == "Stock Split")
            assert txn.date.day == 8  # first date, not the "as of" date

    # -- Sell Short --

    def test_extract_sell_short(self, schwab_csv: Path) -> None:
        with open(schwab_csv, "rb") as f:
            txn = next(t for t in SchwabExtractor(f)() if t.type == "Sell Short")
            assert txn.date.day == 20
            assert txn.amount == Decimal("-2500.00")
            assert txn.extra["symbol"] == "GME"

    # -- Empty amount yields None --

    def test_empty_amount_is_none(self, schwab_csv: Path) -> None:
        """Stock Split and Journal rows have blank Amount fields."""
        with open(schwab_csv, "rb") as f:
            txn = next(t for t in SchwabExtractor(f)() if t.type == "Stock Split")
            assert txn.amount is None

    # -- Quantity commas stripped --

    def test_quantity_commas_stripped(self, schwab_csv: Path) -> None:
        """Quantities like '1,463' should have commas removed."""
        with open(schwab_csv, "rb") as f:
            for txn in SchwabExtractor(f)():
                q = txn.extra.get("quantity", "")
                assert "," not in q
