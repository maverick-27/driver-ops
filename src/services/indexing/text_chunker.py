"""Section-aware chunker. All sizes are in words.

Corpus documents have no abstract, so the chunk header is the document title only.
"""

from src.config import ChunkingSettings
from src.schemas.indexing import TextChunk
from src.schemas.parser import Section

_MAX_SECTION_TITLE = 200


class TextChunker:
    def __init__(self, settings: ChunkingSettings):
        if settings.overlap_size >= settings.chunk_size:
            raise ValueError("overlap_size must be smaller than chunk_size")
        self.chunk_size = settings.chunk_size
        self.overlap_size = settings.overlap_size
        self.min_chunk_size = settings.min_chunk_size
        self.section_min = settings.section_min_words
        self.section_max = settings.section_max_words

    def chunk_document(self, title: str, raw_text: str, sections: list[Section] | None) -> list[TextChunk]:
        header = f"{title}\n\n"
        usable = [s for s in (sections or []) if s.content.strip()]
        bodies = self._from_sections(usable) if usable else self._window(raw_text, "")
        chunks, position = [], 0
        for index, (section_title, body) in enumerate(bodies):
            text = header + (f"Section: {section_title}\n\n" if section_title else "") + body
            chunks.append(
                TextChunk(
                    text=text,
                    chunk_index=index,
                    start_char=position,
                    end_char=position + len(body),
                    word_count=len(text.split()),
                    section_title=section_title[:_MAX_SECTION_TITLE],
                )
            )
            position += len(body)
        return chunks

    def _from_sections(self, sections: list[Section]) -> list[tuple[str, str]]:
        """Return (section_title, body) pairs: mid-sized sections whole, small ones combined, large ones windowed."""
        out: list[tuple[str, str]] = []
        buffer: list[Section] = []

        def flush() -> None:
            if not buffer:
                return
            titles = " / ".join(s.title for s in buffer if s.title)
            body = "\n\n".join(f"{s.title}\n{s.content}" if s.title else s.content for s in buffer)
            # A leftover too small to stand alone joins the previous chunk.
            if out and len(body.split()) < self.section_min:
                prev_title, prev_body = out[-1]
                out[-1] = (prev_title, prev_body + "\n\n" + body)
            else:
                out.append((titles, body))
            buffer.clear()

        for section in sections:
            words = len(section.content.split())
            if words < self.section_min:
                buffered = sum(len(s.content.split()) for s in buffer)
                if buffered + words > self.section_max:
                    flush()
                buffer.append(section)
                continue
            flush()
            if words <= self.section_max:
                out.append((section.title, section.content))
            else:
                parts = self._window(section.content, section.title)
                out.extend((f"{t} (Part {i})" if t else f"Part {i}", body) for i, (t, body) in enumerate(parts, 1))
        flush()
        return out

    def _window(self, text: str, title: str) -> list[tuple[str, str]]:
        """Sliding word window: chunk_size words, advancing chunk_size - overlap_size."""
        words = text.split()
        if not words:
            return []
        if len(words) <= max(self.min_chunk_size, self.chunk_size):
            return [(title, " ".join(words))]
        step = self.chunk_size - self.overlap_size
        out = []
        for start in range(0, len(words), step):
            out.append((title, " ".join(words[start : start + self.chunk_size])))
            if start + self.chunk_size >= len(words):
                break
        return out
