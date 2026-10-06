"""Source client for the Driver Ops corpus.

Regulations are listed in corpus/regulations/manifest.csv and normally already on disk (fetch_corpus.sh).
Company policies are Markdown files with front matter in corpus/company.
"""

import csv
import hashlib
import logging
import time
from pathlib import Path

import httpx

from src.config import CorpusSettings
from src.exceptions import CorpusError
from src.schemas.corpus import CorpusDocument

logger = logging.getLogger(__name__)


def read_front_matter(text: str) -> tuple[dict[str, str], str]:
    """Split '---' delimited 'key: value' front matter from a Markdown body."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    meta: dict[str, str] = {}
    for line in text[3:end].strip().splitlines():
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = value.strip()
    return meta, text[end + 4 :].lstrip("\n")


class CorpusClient:
    def __init__(self, settings: CorpusSettings):
        self.settings = settings
        self.root = Path(settings.root_dir)
        self.regulations_dir = self.root / "regulations"
        self.company_dir = self.root / "company"
        self._last_request = 0.0

    def list_documents(self) -> list[CorpusDocument]:
        return self._list_regulations() + self._list_company()

    def _list_regulations(self) -> list[CorpusDocument]:
        manifest = self.regulations_dir / "manifest.csv"
        if not manifest.exists():
            raise CorpusError(f"Manifest not found: {manifest}")
        documents = []
        with manifest.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                fmt = row["format"].strip().lower()
                documents.append(
                    CorpusDocument(
                        doc_id=row["doc_id"].strip(),
                        title=row["title"].strip(),
                        doc_type="regulation",
                        jurisdiction=row["jurisdiction"].strip(),
                        file_format=fmt,
                        source_url=row["url"].strip(),
                        file_path=str(self.regulations_dir / f"{row['doc_id'].strip()}.{fmt}"),
                    )
                )
        return documents

    def _list_company(self) -> list[CorpusDocument]:
        documents = []
        for path in sorted(self.company_dir.glob("*.md")):
            meta, _ = read_front_matter(path.read_text(encoding="utf-8"))
            doc_id = meta.get("doc_id") or path.stem.split("-")[0]
            documents.append(
                CorpusDocument(
                    doc_id=doc_id,
                    title=meta.get("title", path.stem),
                    doc_type="company_policy",
                    jurisdiction="Company policy",
                    file_format="md",
                    file_path=str(path),
                    extra={k: v for k, v in meta.items() if k in ("version", "effective", "owner")},
                )
            )
        return documents

    def ensure_local(self, document: CorpusDocument) -> Path:
        """Return the local file, downloading it if it is missing and has a source URL."""
        path = Path(document.file_path)
        if path.exists() and path.stat().st_size > 0:
            return path
        if not (self.settings.download_missing and document.source_url):
            raise CorpusError(f"{document.doc_id}: file missing at {path}")
        return self._download(document, path)

    def _download(self, document: CorpusDocument, path: Path) -> Path:
        last_error: Exception | None = None
        for attempt in range(1, self.settings.max_retries + 1):
            wait = self.settings.rate_limit_seconds - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.monotonic()
            try:
                response = httpx.get(
                    document.source_url,
                    headers={"User-Agent": self.settings.user_agent},
                    timeout=self.settings.timeout_seconds,
                    follow_redirects=True,
                )
                response.raise_for_status()
                path.write_bytes(response.content)
                return path
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code < 500 and e.response.status_code != 429:
                    break  # a 403/404 will not change on retry
            except (httpx.HTTPError, OSError) as e:
                last_error = e
            time.sleep(self.settings.retry_delay_seconds * attempt)
        raise CorpusError(f"{document.doc_id}: download failed ({last_error})")

    @staticmethod
    def content_hash(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()
