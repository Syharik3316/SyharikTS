import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any


def _to_bool(raw: str | None, *, default: bool = False) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class LangfuseSettings:
    enabled: bool
    host: str
    public_key: str
    secret_key: str
    environment: str
    release: str


def get_langfuse_settings() -> LangfuseSettings:
    return LangfuseSettings(
        enabled=_to_bool(os.getenv("LANGFUSE_ENABLED"), default=False),
        host=(os.getenv("LANGFUSE_HOST") or "https://cloud.langfuse.com").strip(),
        public_key=(os.getenv("LANGFUSE_PUBLIC_KEY") or "").strip(),
        secret_key=(os.getenv("LANGFUSE_SECRET_KEY") or "").strip(),
        environment=(os.getenv("LANGFUSE_ENV") or "local").strip(),
        release=(os.getenv("LANGFUSE_RELEASE") or "").strip(),
    )


def _create_client(settings: LangfuseSettings) -> Any | None:
    if not settings.enabled or not settings.public_key or not settings.secret_key:
        return None
    try:
        from langfuse import Langfuse
    except Exception:
        return None
    try:
        return Langfuse(
            public_key=settings.public_key,
            secret_key=settings.secret_key,
            host=settings.host,
            environment=settings.environment or None,
            release=settings.release or None,
        )
    except Exception:
        return None


class LangfuseTrace:
    def __init__(self, *, name: str, user_id: str | None, metadata: dict[str, Any] | None = None) -> None:
        self.settings = get_langfuse_settings()
        self._client = _create_client(self.settings)
        self._trace = None
        self._name = name
        self._trace_id = str(uuid.uuid4())
        if self._client is None:
            return
        try:
            self._trace = self._client.trace(
                id=self._trace_id,
                name=name,
                user_id=user_id,
                metadata=metadata or {},
            )
        except Exception:
            self._trace = None

    @property
    def trace_id(self) -> str:
        return self._trace_id

    @contextmanager
    def span(self, name: str, *, input_data: Any | None = None, metadata: dict[str, Any] | None = None):
        started = time.perf_counter()
        span_obj = None
        if self._trace is not None:
            try:
                span_obj = self._trace.span(name=name, input=input_data, metadata=metadata or {})
            except Exception:
                span_obj = None
        error: Exception | None = None
        try:
            yield
        except Exception as exc:
            error = exc
            raise
        finally:
            duration_ms = int((time.perf_counter() - started) * 1000)
            if span_obj is not None:
                try:
                    if error is None:
                        span_obj.end(metadata={"duration_ms": duration_ms})
                    else:
                        span_obj.end(level="ERROR", status_message=str(error), metadata={"duration_ms": duration_ms})
                except Exception:
                    pass
            if self._client is not None:
                try:
                    self._client.flush()
                except Exception:
                    pass


def build_safe_prompt_preview(prompt: str, *, max_chars: int = 1200) -> str:
    compact = " ".join(prompt.split())
    if len(compact) <= max_chars:
        return compact
    return f"{compact[:max_chars]}..."
