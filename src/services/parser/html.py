"""HTML parser: main content only, split into sections at headings."""

import re
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from src.exceptions import DocumentRejected
from src.schemas.parser import ParsedContent, Section

_BOILERPLATE_TAGS = ["script", "style", "noscript", "nav", "header", "footer", "aside", "form", "svg", "button", "iframe"]
# Matched against each class/id token as a whole, so "toc-end" or "skip-main-content" on a content wrapper is kept.
_BOILERPLATE_TOKEN = re.compile(r"^(.*breadcrumbs?.*|.*pagination.*|pager|toc|table-of-contents|on-this-page.*|.*sidebar.*|skip-links?)$", re.I)
_BLOCK_TAGS = ["p", "li", "tr", "div", "section", "article", "dt", "dd", "blockquote", "pre", "caption", "br", "ul", "ol", "table"]
_HEADING = re.compile(r"^h[1-6]$")
_SKIP_SECTION_TITLES = re.compile(r"^(table of contents|table of figures|revision history)", re.I)
# The in-page index heading; its link list is navigation, but on short pages the body text follows it directly.
_INDEX_TITLE = re.compile(r"^on this page", re.I)
_MARK = "\x00"


class HTMLParser:
    def __init__(self, min_words: int = 30):
        self.min_words = min_words

    def parse(self, path: Path) -> ParsedContent:
        soup = BeautifulSoup(path.read_bytes(), "lxml")
        page_title = soup.title.get_text(strip=True) if soup.title else ""
        root = soup.find("main") or soup.find(attrs={"role": "main"}) or soup.body
        if root is None:
            raise DocumentRejected("no <main> or <body> element")

        for tag in root.find_all(_BOILERPLATE_TAGS):
            tag.decompose()
        for tag in root.find_all(True):
            if not isinstance(tag, Tag) or tag.attrs is None:
                continue
            tokens = [*(tag.get("class") or []), tag.get("id") or ""]
            if any(_BOILERPLATE_TOKEN.match(t) for t in tokens) or tag.get("role") == "navigation":
                tag.decompose()

        # Turn structure into text markers, then split once.
        for cell in root.find_all(["td", "th"]):
            cell.append(" | ")
        for heading in root.find_all(_HEADING):
            title = " ".join(heading.get_text(" ").split())
            heading.replace_with(f"\n{_MARK}{heading.name[1]}{_MARK}{title}{_MARK}\n")
        for block in root.find_all(_BLOCK_TAGS):
            block.insert_before("\n")
            block.insert_after("\n")

        sections = self._split(root.get_text())
        raw_text = "\n\n".join(f"{s.title}\n{s.content}" if s.title else s.content for s in sections)
        words = len(raw_text.split())
        if words < self.min_words:
            raise DocumentRejected(
                f"only {words} words of body text (minimum {self.min_words}); the page is probably rendered by JavaScript"
            )
        return ParsedContent(
            raw_text=raw_text,
            sections=sections,
            parser_used="html",
            metadata={"page_title": page_title, "words": words, "sections": len(sections)},
        )

    @staticmethod
    def _clean(text: str) -> str:
        lines = [" ".join(line.split()) for line in text.splitlines()]
        return "\n".join(line for line in lines if line and line != "|")

    def _split(self, text: str) -> list[Section]:
        parts = re.split(f"{_MARK}(\\d){_MARK}([^{_MARK}]*){_MARK}", text)
        sections: list[Section] = []
        preamble = self._clean(parts[0])
        if preamble:
            sections.append(Section(title="", content=preamble, level=1))
        for i in range(1, len(parts), 3):
            level, title, content = int(parts[i]), parts[i + 1].strip(), self._clean(parts[i + 2])
            if _SKIP_SECTION_TITLES.match(title):
                continue
            if _INDEX_TITLE.match(title):
                title = ""
            if content or title:
                sections.append(Section(title=title, content=content, level=level))
        # A heading with no body (e.g. an h1 directly followed by an h2) carries no text of its own.
        return [s for s in sections if s.content]
