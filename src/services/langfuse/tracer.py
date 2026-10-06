"""Langfuse v3 wrapper. Every method is a no-op when tracing is disabled, and no tracing error reaches a request."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from src.config import LangfuseSettings

logger = logging.getLogger(__name__)


class _NoopSpan:
    def update(self, **_: Any) -> None:
        pass


class _SafeSpan:
    def __init__(self, span: Any):
        self._span = span

    def update(self, **kwargs: Any) -> None:
        try:
            self._span.update(**kwargs)
        except Exception as e:
            logger.warning("Langfuse span update failed: %s", e)


class LangfuseTracer:
    def __init__(self, settings: LangfuseSettings):
        self.client = None
        if settings.enabled and settings.public_key and settings.secret_key:
            try:
                from langfuse import Langfuse

                self.client = Langfuse(public_key=settings.public_key, secret_key=settings.secret_key, host=settings.host)
            except Exception as e:
                logger.warning("Langfuse disabled, client could not be created: %s", e)

    @property
    def enabled(self) -> bool:
        return self.client is not None

    @contextmanager
    def _observe(self, kind: str, name: str, **kwargs: Any) -> Iterator[Any]:
        if self.client is None:
            yield _NoopSpan()
            return
        try:
            start = self.client.start_as_current_generation if kind == "generation" else self.client.start_as_current_span
            manager = start(name=name, **kwargs)
            span = manager.__enter__()
        except Exception as e:
            logger.warning("Langfuse %s '%s' not started: %s", kind, name, e)
            yield _NoopSpan()
            return
        try:
            yield _SafeSpan(span)
        finally:
            try:
                manager.__exit__(None, None, None)
            except Exception as e:
                logger.warning("Langfuse %s '%s' not closed: %s", kind, name, e)

    def span(self, name: str, input: Any = None, metadata: dict[str, Any] | None = None):
        """A span nested under whichever span is current. The outermost one of a request is the trace root."""
        return self._observe("span", name, input=input, metadata=metadata)

    def generation(self, name: str, model: str, input: Any = None):
        return self._observe("generation", name, model=model, input=input)

    def current_trace_id(self) -> str | None:
        if self.client is None:
            return None
        try:
            return self.client.get_current_trace_id()
        except Exception:
            return None

    def update_trace(self, **kwargs: Any) -> None:
        if self.client is None:
            return
        try:
            self.client.update_current_trace(**kwargs)
        except Exception as e:
            logger.warning("Langfuse trace update failed: %s", e)

    def score(self, trace_id: str, name: str, value: float, comment: str | None = None) -> bool:
        if self.client is None:
            return False
        try:
            self.client.create_score(trace_id=trace_id, name=name, value=value, comment=comment)
            return True
        except Exception as e:
            logger.warning("Langfuse score failed: %s", e)
            return False

    def flush(self) -> None:
        if self.client is not None:
            try:
                self.client.flush()
            except Exception as e:
                logger.warning("Langfuse flush failed: %s", e)
