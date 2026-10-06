from src.config import get_settings
from src.services.corpus.client import CorpusClient


def make_corpus_client() -> CorpusClient:
    return CorpusClient(get_settings().corpus)
