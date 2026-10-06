"""Typed settings. Nested settings use a double underscore: OPENSEARCH__HOST, LANGFUSE__PUBLIC_KEY."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE_PATH = PROJECT_ROOT / ".env"

# Bump when any prompt changes; it is part of the cache key.
PROMPT_VERSION = "v3"


def _config(prefix: str = "") -> SettingsConfigDict:
    return SettingsConfigDict(
        env_prefix=prefix,
        env_file=[".env", str(ENV_FILE_PATH)],
        extra="ignore",
        frozen=True,
        env_nested_delimiter="__",
        case_sensitive=False,
    )


class OpenSearchSettings(BaseSettings):
    model_config = _config("OPENSEARCH__")
    host: str = "http://localhost:9200"
    index_name: str = "driver-ops"
    chunk_index_suffix: str = "chunks"
    vector_dimension: int = 1024
    rrf_pipeline_name: str = "hybrid-rrf-pipeline"
    # Candidates each sub-query (BM25, kNN) hands to RRF. Measured on evals/questions.yaml at top_k 5:
    # 10 -> 15/18 hits, 15-20 -> 16/18, 30-100 -> 15/18. Re-measure when the corpus or eval set changes.
    hybrid_candidates: int = 20

    @property
    def chunk_index(self) -> str:
        return f"{self.index_name}-{self.chunk_index_suffix}"


class EmbeddingsSettings(BaseSettings):
    model_config = _config("EMBEDDINGS__")
    # "ollama" keeps company documents on this machine; "jina" sends text to a hosted API; "none" is BM25 only.
    provider: Literal["ollama", "jina", "none"] = "ollama"
    host: str = "http://localhost:11434"
    model: str = "bge-m3"
    jina_api_key: str = ""
    dimensions: int = 1024
    batch_size: int = 16
    timeout_seconds: float = 60.0
    retries: int = 3
    query_timeout_seconds: float = 5.0
    query_retries: int = 0


class CorpusSettings(BaseSettings):
    model_config = _config("CORPUS__")
    root_dir: str = str(PROJECT_ROOT / "corpus")
    rate_limit_seconds: float = 3.0
    timeout_seconds: float = 60.0
    max_retries: int = 3
    retry_delay_seconds: float = 5.0
    download_missing: bool = True
    user_agent: str = "Mozilla/5.0 (DriverOps corpus fetch; personal research)"


class ParserSettings(BaseSettings):
    model_config = _config("PARSER__")
    max_pages: int = 100
    max_file_size_mb: int = 20
    do_ocr: bool = False
    do_table_structure: bool = True
    # A page with fewer body words than this is treated as a failed parse (e.g. a JavaScript shell).
    min_words: int = 30


class ChunkingSettings(BaseSettings):
    model_config = _config("CHUNKING__")
    chunk_size: int = 600
    overlap_size: int = 100
    min_chunk_size: int = 100
    section_min_words: int = 100
    section_max_words: int = 800


class LangfuseSettings(BaseSettings):
    model_config = _config("LANGFUSE__")
    enabled: bool = False
    public_key: str = ""
    secret_key: str = ""
    host: str = "http://localhost:3001"


class RedisSettings(BaseSettings):
    model_config = _config("REDIS__")
    host: str = "localhost"
    port: int = 6379
    password: str = ""
    db: int = 0
    ttl_hours: int = 6


class TelegramSettings(BaseSettings):
    model_config = _config("TELEGRAM__")
    enabled: bool = False
    bot_token: str = ""
    api_base_url: str = "http://localhost:8000"
    # Comma-separated Telegram user ids allowed to use the bot. Empty means nobody is allowed.
    allowed_user_ids: str = ""
    history_ttl_seconds: int = 600

    @property
    def allowed_ids(self) -> set[int]:
        return {int(x) for x in self.allowed_user_ids.split(",") if x.strip()}


class AgentSettings(BaseSettings):
    model_config = _config("AGENT__")
    top_k: int = 5
    max_retrieval_attempts: int = 2
    guardrail_threshold: int = 60
    temperature: float = 0.0
    rewrite_temperature: float = 0.3


class Settings(BaseSettings):
    model_config = _config()
    environment: Literal["development", "staging", "production"] = "development"
    app_version: str = "0.1.0"
    postgres_database_url: str = "postgresql+psycopg2://driver_ops:driver_ops@localhost:5442/driver_ops"
    # Shared secret for every endpoint except health. Empty disables the check (development only).
    api_key: str = ""

    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "gemma3:4b"
    ollama_timeout: float = 120.0
    ollama_num_ctx: int = 8192
    ollama_keep_alive: str = "30m"
    ollama_num_predict_default: int = -1
    ollama_num_predict_structured: int = 256

    opensearch: OpenSearchSettings = Field(default_factory=OpenSearchSettings)
    embeddings: EmbeddingsSettings = Field(default_factory=EmbeddingsSettings)
    corpus: CorpusSettings = Field(default_factory=CorpusSettings)
    parser: ParserSettings = Field(default_factory=ParserSettings)
    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)
    langfuse: LangfuseSettings = Field(default_factory=LangfuseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
