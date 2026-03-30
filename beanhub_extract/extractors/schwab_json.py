import datetime
import decimal
import hashlib
import json
import typing

from ..data_types import Fingerprint
from ..data_types import Transaction
from ..text import as_text
from .base import ExtractorBase

EXPECTED_KEYS = frozenset(
    {
        "Date",
        "Action",
        "Symbol",
        "Description",
        "Quantity",
        "Price",
        "Fees & Comm",
        "Amount",
        "AcctgRuleCd",
    }
)


def parse_date(date_str: str) -> datetime.date:
    """Parse date in MM/DD/YYYY format, ignoring any 'as of' suffix."""
    date_str = date_str.split(" as of ")[0].strip()
    parts = date_str.split("/")
    return datetime.date(int(parts[2]), int(parts[0]), int(parts[1]))


def parse_amount(amount_str: str) -> decimal.Decimal | None:
    """Parse dollar amount like '$1,234.56' or '-$1,234.56'.

    Returns None for empty/blank strings.
    """
    cleaned = amount_str.replace("$", "").replace(",", "").strip()
    if not cleaned:
        return None
    return decimal.Decimal(cleaned)


def parse_quantity(quantity_str: str) -> str:
    """Clean quantity string by removing commas."""
    return quantity_str.replace(",", "").strip()


def is_valid_row(row: dict) -> bool:
    """A row is valid if it has a parseable date and a non-empty action."""
    date_str = row.get("Date", "").strip()
    if not date_str:
        return False
    try:
        parse_date(date_str)
    except (ValueError, IndexError):
        return False
    return bool(row.get("Action", "").strip())


def generate_transaction_id(row: dict) -> str:
    """Stable hash from the key fields of a row."""
    parts = [
        row.get("Date", ""),
        row.get("Action", ""),
        row.get("Symbol", ""),
        row.get("Description", ""),
        row.get("Quantity", ""),
        row.get("Price", ""),
        row.get("Amount", ""),
        row.get("AcctgRuleCd", ""),
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]


def resolve_type(action: str, acctg_rule_cd: str) -> str:
    """Determine the transaction type from Action and AcctgRuleCd.

    AcctgRuleCd "6" on a Buy action indicates a short cover (buying to close
    a short position).  All other actions are returned as-is.
    """
    if action == "Buy" and acctg_rule_cd == "6":
        return "Buy to Cover"
    return action


class SchwabJsonExtractor(ExtractorBase):
    """Extractor for Charles Schwab brokerage JSON exports.

    JSON format::

        {
          "BrokerageTransactions": [
            {
              "Date": "MM/DD/YYYY",
              "Action": "...",
              "Symbol": "...",
              "Description": "...",
              "Quantity": "...",
              "Price": "...",
              "Fees & Comm": "...",
              "Amount": "...",
              "AcctgRuleCd": "..."
            },
            ...
          ]
        }

    * Dates are MM/DD/YYYY, optionally with an " as of MM/DD/YYYY" suffix.
    * Dollar values are prefixed with ``$`` and use commas for thousands.
    * Quantity may also contain commas.
    * ``AcctgRuleCd`` "6" on a ``Buy`` action is mapped to type ``Buy to Cover``.
    """

    EXTRACTOR_NAME = "schwab_json"
    DEFAULT_IMPORT_ID = "{{ transaction_id }}"

    def _load(self) -> dict | None:
        """Try to load and validate the JSON structure. Returns parsed dict or None."""
        self.input_file.seek(0)
        try:
            with as_text(self.input_file) as text_file:
                data = json.load(text_file)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        txns = data.get("BrokerageTransactions")
        if not isinstance(txns, list):
            return None
        return data

    def detect(self) -> bool:
        data = self._load()
        if data is None:
            return False
        txns = data["BrokerageTransactions"]
        if not txns:
            # Empty transaction list — could be valid but we can't confirm
            return False
        first = txns[0]
        if not isinstance(first, dict):
            return False
        return EXPECTED_KEYS.issubset(first.keys())

    def fingerprint(self) -> Fingerprint | None:
        data = self._load()
        if data is None:
            return None
        rows = [r for r in data["BrokerageTransactions"] if is_valid_row(r)]
        if not rows:
            return None
        first = rows[0]
        h = hashlib.sha256()
        for key in sorted(first.keys()):
            h.update(first.get(key, "").encode())
        return Fingerprint(
            starting_date=parse_date(first["Date"]),
            first_row_hash=h.hexdigest(),
        )

    def __call__(self) -> typing.Generator[Transaction, None, None]:
        data = self._load()
        if data is None:
            return

        filename = getattr(self.input_file, "name", None)
        if filename is not None and not isinstance(filename, str):
            filename = str(filename)

        rows = [r for r in data["BrokerageTransactions"] if is_valid_row(r)]
        total = len(rows)

        for i, row in enumerate(rows):
            date = parse_date(row["Date"])
            action = row.get("Action", "").strip()
            symbol = row.get("Symbol", "").strip()
            description = row.get("Description", "").strip()
            amount = parse_amount(row.get("Amount", ""))
            quantity = parse_quantity(row.get("Quantity", ""))
            price_raw = (
                row.get("Price", "").replace("$", "").replace(",", "").strip()
            )
            fees = parse_amount(row.get("Fees & Comm", ""))
            acctg_rule_cd = row.get("AcctgRuleCd", "").strip()

            txn_type = resolve_type(action, acctg_rule_cd)

            yield Transaction(
                extractor=self.EXTRACTOR_NAME,
                file=filename,
                lineno=i + 1,
                reversed_lineno=i - total,
                transaction_id=generate_transaction_id(row),
                date=date,
                desc=f"{txn_type} - {description}" if description else txn_type,
                bank_desc=description,
                amount=amount,
                currency="USD",
                type=txn_type,
                extra={
                    "symbol": symbol,
                    "quantity": quantity,
                    "price": price_raw,
                    "fees_comm": str(fees) if fees else "",
                    "acctg_rule_cd": acctg_rule_cd,
                },
            )
