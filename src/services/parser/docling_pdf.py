"""PDF parser on Docling. Size and page limits are checked before parsing."""

import logging
from pathlib import Path

from src.config import ParserSettings
from src.exceptions import DocumentRejected, ParsingError
from src.schemas.parser import ParsedContent, Section

logger = logging.getLogger(__name__)


class DoclingPDFParser:
    def __init__(self, settings: ParserSettings):
        self.settings = settings
        self._converter = None  # built on first use: loading Docling models is slow

    def _get_converter(self):
        if self._converter is None:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption

            options = PdfPipelineOptions(do_ocr=self.settings.do_ocr, do_table_structure=self.settings.do_table_structure)
            self._converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
        return self._converter

    def _validate(self, path: Path) -> int:
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > self.settings.max_file_size_mb:
            raise DocumentRejected(f"PDF is {size_mb:.1f} MB (limit {self.settings.max_file_size_mb} MB)")
        with path.open("rb") as f:
            if not f.read(8).startswith(b"%PDF-"):
                raise DocumentRejected("file does not start with a PDF header")
        import pypdfium2  # installed with Docling

        pdf = pypdfium2.PdfDocument(str(path))
        try:
            pages = len(pdf)
        finally:
            pdf.close()
        if pages > self.settings.max_pages:
            raise DocumentRejected(f"PDF has {pages} pages (limit {self.settings.max_pages})")
        return pages

    def parse(self, path: Path) -> ParsedContent:
        pages = self._validate(path)
        try:
            result = self._get_converter().convert(
                str(path), max_num_pages=self.settings.max_pages, max_file_size=self.settings.max_file_size_mb * 1024 * 1024
            )
        except Exception as e:
            raise ParsingError(f"Docling failed: {e}") from e

        document = result.document
        sections: list[Section] = []
        current = {"title": "", "content": []}
        for element in document.texts:
            label = getattr(getattr(element, "label", None), "value", str(getattr(element, "label", "")))
            text = (getattr(element, "text", "") or "").strip()
            if not text or label in ("page_header", "page_footer"):
                continue
            if label in ("title", "section_header"):
                if current["content"]:
                    sections.append(Section(title=current["title"], content="\n".join(current["content"])))
                current = {"title": text, "content": []}
            else:
                current["content"].append(text)
        if current["content"]:
            sections.append(Section(title=current["title"], content="\n".join(current["content"])))

        raw_text = document.export_to_text()
        words = len(raw_text.split())
        if words < self.settings.min_words:
            raise DocumentRejected(f"only {words} words extracted; the PDF may be scanned (OCR is off)")
        return ParsedContent(
            raw_text=raw_text,
            sections=sections,
            parser_used="docling",
            metadata={"pages": pages, "words": words, "sections": len(sections)},
        )
