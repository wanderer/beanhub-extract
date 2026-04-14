import io
import os
import typing

from .base import ExtractorBase
from .chase import ChaseCreditCardExtractor
from .chase_brokerage import ChaseBrokerageExtractor
from .citi import CitiCreditCardExtractor
from .csv import CSVExtractor
from .fidelity import FidelityExtractor
from .mercury import MercuryExtractor
from .plaid import PlaidExtractor
from .schwab import SchwabExtractor
from .schwab_json import SchwabJsonExtractor
from .revolut import RevolutExtractor
from .wealthsimple import WealthsimpleExtractor

ALL_EXTRACTORS: dict[str, typing.Type[ExtractorBase]] = {
    MercuryExtractor.EXTRACTOR_NAME: MercuryExtractor,
    ChaseCreditCardExtractor.EXTRACTOR_NAME: ChaseCreditCardExtractor,
    ChaseBrokerageExtractor.EXTRACTOR_NAME: ChaseBrokerageExtractor,
    PlaidExtractor.EXTRACTOR_NAME: PlaidExtractor,
    WealthsimpleExtractor.EXTRACTOR_NAME: WealthsimpleExtractor,
    CSVExtractor.EXTRACTOR_NAME: CSVExtractor,
    FidelityExtractor.EXTRACTOR_NAME: FidelityExtractor,
    CitiCreditCardExtractor.EXTRACTOR_NAME: CitiCreditCardExtractor,
    SchwabExtractor.EXTRACTOR_NAME: SchwabExtractor,
    SchwabJsonExtractor.EXTRACTOR_NAME: SchwabJsonExtractor,
    RevolutExtractor.EXTRACTOR_NAME: RevolutExtractor,
}


def detect_extractor(
    input_file: typing.TextIO | typing.BinaryIO,
) -> typing.Type[ExtractorBase]:
    for extractor_cls in ALL_EXTRACTORS.values():
        input_file.seek(os.SEEK_SET)
        if extractor_cls(input_file).detect():
            return extractor_cls
