"""Markdown parser for company policy documents: front matter dropped, sections split at headings."""

import re
from pathlib import Path

from src.exceptions import DocumentRejected
from src.schemas.parser import ParsedContent, Section
from src.services.corpus.client import read_front_matter

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


class MarkdownParser:
    def __init__(self, min_words: int = 30):
        self.min_words = min_words

    def parse(self, path: Path) -> ParsedContent:
        meta, body = read_front_matter(path.read_text(encoding="utf-8"))
        sections: list[Section] = []
        title, level, lines = "", 1, []

        def flush() -> None:
            content = "\n".join(lines).strip()
            if content:
                sections.append(Section(title=title, content=content, level=level))

        for line in body.splitlines():
            match = _HEADING.match(line)
            if match:
                flush()
                title, level, lines = match.group(2).strip(), len(match.group(1)), []
            else:
                lines.append(line)
        flush()

        raw_text = "\n\n".join(f"{s.title}\n{s.content}" if s.title else s.content for s in sections)
        words = len(raw_text.split())
        if words < self.min_words:
            raise DocumentRejected(f"only {words} words of body text (minimum {self.min_words})")
        return ParsedContent(
            raw_text=raw_text,
            sections=sections,
            parser_used="markdown",
            metadata={"front_matter": meta, "words": words, "sections": len(sections)},
        )
