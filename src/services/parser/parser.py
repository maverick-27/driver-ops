from pathlib import Path

from src.config import ParserSettings
from src.exceptions import ParsingError
from src.schemas.parser import ParsedContent
from src.services.parser.docling_pdf import DoclingPDFParser
from src.services.parser.html import HTMLParser
from src.services.parser.markdown import MarkdownParser


class DocumentParser:
    """Routes a file to the parser for its format."""

    def __init__(self, settings: ParserSettings):
        self._parsers = {
            "pdf": DoclingPDFParser(settings),
            "html": HTMLParser(min_words=settings.min_words),
            "md": MarkdownParser(min_words=settings.min_words),
        }

    def parse(self, path: Path, file_format: str) -> ParsedContent:
        parser = self._parsers.get(file_format)
        if parser is None:
            raise ParsingError(f"No parser for format '{file_format}'")
        return parser.parse(path)
