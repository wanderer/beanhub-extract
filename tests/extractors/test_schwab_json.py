from decimal import Decimal
from pathlib import Path

import pytest

from beanhub_extract.extractors.schwab_json import SchwabJsonExtractor


@pytest.fixture
def schwab_json(fixtures_folder: Path) -> Path:
    return fixtures_folder / "schwab.json"


class TestSchwabJsonExtractor:
    """Tests for Schwab brokerage JSON extractor."""

    def test_detect(self, schwab_json: Path) -> None:
        with open(schwab_json, "rb") as f:
            assert SchwabJsonExtractor(f).detect() is True

    def test_detect_wrong_format(self, fixtures_folder: Path) -> None:
        with open(fixtures_folder / "mercury.csv", "rb") as f:
            assert SchwabJsonExtractor(f).detect() is False

    def test_detect_csv_not_json(self, fixtures_folder: Path) -> None:
        with open(fixtures_folder / "schwab.csv", "rb") as f:
            assert SchwabJsonExtractor(f).detect() is False

    def test_fingerprint(self, schwab_json: Path) -> None:
        with open(schwab_json, "rb") as f:
            fp = SchwabJsonExtractor(f).fingerprint()
            assert fp is not None
            assert fp.starting_date.year == 2026
            assert fp.starting_date.month == 1
            assert fp.starting_date.day == 2
            assert isinstance(fp.first_row_hash, str)
            assert len(fp.first_row_hash) > 0

    def test_extract_all_transactions(self, schwab_json: Path) -> None:
        with open(schwab_json, "rb") as f:
            txns = list(SchwabJsonExtractor(f)())
            assert len(txns) == 11

    def test_currency(self, schwab_json: Path) -> None:
        with open(schwab_json, "rb") as f:
            for txn in SchwabJsonExtractor(f)():
                assert txn.currency == "USD"

    def test_transaction_id_populated(self, schwab_json: Path) -> None:
        """Every transaction must have a non-empty transaction_id."""
        with open(schwab_json, "rb") as f:
            for txn in SchwabJsonExtractor(f)():
                assert txn.transaction_id is not None
                assert len(txn.transaction_id) == 32

    def test_transaction_ids_unique(self, schwab_json: Path) -> None:
        """All transaction IDs should be distinct."""
        with open(schwab_json, "rb") as f:
            ids = [txn.transaction_id for txn in SchwabJsonExtractor(f)()]
            assert len(ids) == len(set(ids))

    def test_lineno_and_reversed_lineno(self, schwab_json: Path) -> None:
        with open(schwab_json, "rb") as f:
            txns = list(SchwabJsonExtractor(f)())
            assert txns[0].lineno == 1
            assert txns[0].reversed_lineno == -11
            assert txns[-1].lineno == 11
            assert txns[-1].reversed_lineno == -1

    # -- Dividend --

    def test_extract_dividend(self, schwab_json: Path) -> None:
        with open(schwab_json, "rb") as f:
            txn = list(SchwabJsonExtractor(f)())[0]
            assert txn.type == "Qualified Dividend"
            assert txn.date.year == 2026
            assert txn.date.month == 1
            assert txn.date.day == 2
            assert txn.amount == Decimal("12.50")
            assert txn.extra["symbol"] == "AAPL"
            assert txn.desc == "Qualified Dividend - APPLE INC"
            assert txn.bank_desc == "APPLE INC"
            assert txn.extra["acctg_rule_cd"] == "2"

    # -- Buy --

    def test_extract_buy(self, schwab_json: Path) -> None:
        with open(schwab_json, "rb") as f:
            buy = next(t for t in SchwabJsonExtractor(f)() if t.type == "Buy")
            assert buy.date.day == 3
            assert buy.amount == Decimal("-1500.00")
            assert buy.extra["symbol"] == "AAPL"
            assert buy.extra["quantity"] == "10"
            assert buy.extra["price"] == "150.00"
            assert buy.desc == "Buy - APPLE INC"
            assert buy.extra["acctg_rule_cd"] == "1"

    # -- Sell --

    def test_extract_sell(self, schwab_json: Path) -> None:
        with open(schwab_json, "rb") as f:
            sell = next(t for t in SchwabJsonExtractor(f)() if t.type == "Sell")
            assert sell.date.day == 5
            assert sell.amount == Decimal("799.50")
            assert sell.extra["quantity"] == "5"
            assert sell.extra["price"] == "160.00"
            assert sell.extra["fees_comm"] == "0.50"

    # -- Credit Interest --

    def test_extract_credit_interest(self, schwab_json: Path) -> None:
        with open(schwab_json, "rb") as f:
            txn = next(
                t for t in SchwabJsonExtractor(f)() if t.type == "Credit Interest"
            )
            assert txn.date.day == 6
            assert txn.amount == Decimal("0.25")

    # -- Advisor Fee --

    def test_extract_advisor_fee(self, schwab_json: Path) -> None:
        with open(schwab_json, "rb") as f:
            txn = next(
                t for t in SchwabJsonExtractor(f)() if t.type == "Advisor Fee"
            )
            assert txn.date.day == 7
            assert txn.amount == Decimal("-45.00")

    # -- "as of" date handling --

    def test_extract_date_with_as_of(self, schwab_json: Path) -> None:
        with open(schwab_json, "rb") as f:
            txn = next(
                t for t in SchwabJsonExtractor(f)() if t.type == "Stock Split"
            )
            assert txn.date.day == 8  # first date, not the "as of" date

    # -- Sell Short --

    def test_extract_sell_short(self, schwab_json: Path) -> None:
        with open(schwab_json, "rb") as f:
            txn = next(
                t for t in SchwabJsonExtractor(f)() if t.type == "Sell Short"
            )
            assert txn.date.day == 20
            assert txn.amount == Decimal("-2500.00")
            assert txn.extra["symbol"] == "GME"
            assert txn.extra["acctg_rule_cd"] == "6"

    # -- Buy to Cover (AcctgRuleCd=6 on Buy) --

    def test_extract_buy_to_cover(self, schwab_json: Path) -> None:
        """Buy with AcctgRuleCd=6 should be mapped to 'Buy to Cover'."""
        with open(schwab_json, "rb") as f:
            txn = next(
                t for t in SchwabJsonExtractor(f)() if t.type == "Buy to Cover"
            )
            assert txn.date.day == 22
            assert txn.amount == Decimal("-2000.00")
            assert txn.extra["symbol"] == "GME"
            assert txn.extra["quantity"] == "100"
            assert txn.extra["price"] == "20.00"
            assert txn.extra["acctg_rule_cd"] == "6"
            assert txn.desc == "Buy to Cover - GAMESTOP CORP"

    # -- Empty amount yields None --

    def test_empty_amount_is_none(self, schwab_json: Path) -> None:
        """Stock Split and Journal rows have blank Amount fields."""
        with open(schwab_json, "rb") as f:
            txn = next(
                t for t in SchwabJsonExtractor(f)() if t.type == "Stock Split"
            )
            assert txn.amount is None

    # -- Quantity commas stripped --

    def test_quantity_commas_stripped(self, schwab_json: Path) -> None:
        """Quantities like '1,463' should have commas removed."""
        with open(schwab_json, "rb") as f:
            for txn in SchwabJsonExtractor(f)():
                q = txn.extra.get("quantity", "")
                assert "," not in q

    # -- acctg_rule_cd is always in extra --

    def test_acctg_rule_cd_in_extra(self, schwab_json: Path) -> None:
        """Every transaction should have acctg_rule_cd in extra dict."""
        with open(schwab_json, "rb") as f:
            for txn in SchwabJsonExtractor(f)():
                assert "acctg_rule_cd" in txn.extra
