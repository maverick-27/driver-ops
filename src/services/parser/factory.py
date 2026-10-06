from functools import lru_cache

from src.config import get_settings
from src.services.parser.parser import DocumentParser


@lru_cache(maxsize=1)
def make_document_parser() -> DocumentParser:
    return DocumentParser(get_settings().parser)
