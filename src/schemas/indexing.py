from pydantic import BaseModel


class TextChunk(BaseModel):
    text: str
    chunk_index: int
    start_char: int
    end_char: int
    word_count: int
    section_title: str = ""
