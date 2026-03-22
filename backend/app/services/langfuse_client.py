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


def _stringify_metadata(meta: dict[str, Any]) -> dict[str, str]:
    """Langfuse v4: propagated metadata is dict[str, str], values ≤200 chars."""
    out: dict[str, str] = {}
    for k, v in meta.items():
        sk = str(k)[:200]
        sv = str(v)[:200]
        out[sk] = sv
    return out


@dataclass(frozen=True)
class LangfuseSettings:
    enabled: bool
    base_url: str
    public_key: str
    secret_key: str
    environment: str
    release: str

    @property
    def host(self) -> str:
        """Alias for observability API (same URL as base_url)."""
        return self.base_url


def get_langfuse_settings() -> LangfuseSettings:
    base = (
        os.getenv("LANGFUSE_BASE_URL") or os.getenv("LANGFUSE_HOST") or "https://cloud.langfuse.com"
    ).strip()
    return LangfuseSettings(
        enabled=_to_bool(os.getenv("LANGFUSE_ENABLED"), default=False),
        base_url=base,
        public_key=(os.getenv("LANGFUSE_PUBLIC_KEY") or "").strip(),
        secret_key=(os.getenv("LANGFUSE_SECRET_KEY") or "").strip(),
        environment=(os.getenv("LANGFUSE_ENV") or os.getenv("LANGFUSE_TRACING_ENVIRONMENT") or "local").strip(),
        release=(os.getenv("LANGFUSE_RELEASE") or "").strip(),
    )


def _apply_langfuse_env(settings: LangfuseSettings) -> None:
    """SDK v4 reads LANGFUSE_* env; keep in sync for get_client() / Langfuse()."""
    if not (settings.enabled and settings.public_key and settings.secret_key):
        return
    os.environ["LANGFUSE_PUBLIC_KEY"] = settings.public_key
    os.environ["LANGFUSE_SECRET_KEY"] = settings.secret_key
    os.environ["LANGFUSE_BASE_URL"] = settings.base_url
    if settings.environment:
        os.environ["LANGFUSE_TRACING_ENVIRONMENT"] = settings.environment
    if settings.release:
        os.environ["LANGFUSE_RELEASE"] = settings.release


def _create_langfuse_client(settings: LangfuseSettings) -> Any | None:
    if not settings.enabled or not settings.public_key or not settings.secret_key:
        return None
    try:
        from langfuse import Langfuse
    except Exception:
        return None
    kwargs: dict[str, Any] = {
        "public_key": settings.public_key,
        "secret_key": settings.secret_key,
        "base_url": settings.base_url,
    }
    try:
        # v4: export custom spans (not only gen_ai); safe for self-hosted.
        return Langfuse(**kwargs, should_export_span=lambda _span: True)
    except TypeError:
        try:
            return Langfuse(**kwargs)
        except Exception:
            return None
    except Exception:
        return None


class LangfuseTrace:
    """
    Request-scoped trace for Langfuse SDK v4 (OpenTelemetry-based).

    Must be used as a context manager so the root observation stays active and
    child spans can attach (including from worker threads via explicit parent).
    """

    def __init__(self, *, name: str, user_id: str | None, metadata: dict[str, Any] | None = None) -> None:
        self.settings = get_langfuse_settings()
        self._name = name
        self._user_id = user_id
        self._metadata = _stringify_metadata(metadata or {})
        self._trace_id = str(uuid.uuid4())
        self._lf: Any | None = None
        self._root_cm: Any | None = None
        self._root_span: Any | None = None
        self._prop_cm: Any | None = None
        self._credentials_ok = bool(
            self.settings.enabled and self.settings.public_key and self.settings.secret_key
        )

    @property
    def trace_id(self) -> str:
        return self._trace_id

    def __enter__(self) -> "LangfuseTrace":
        if not self._credentials_ok:
            return self
        try:
            from langfuse import propagate_attributes
        except Exception:
            return self
        _apply_langfuse_env(self.settings)
        self._lf = _create_langfuse_client(self.settings)
        if self._lf is None:
            return self
        try:
            prop_kwargs: dict[str, Any] = {"trace_name": self._name, "metadata": self._metadata}
            if self._user_id:
                prop_kwargs["user_id"] = str(self._user_id)[:200]
            self._root_cm = self._lf.start_as_current_observation(as_type="span", name=self._name)
            self._root_span = self._root_cm.__enter__()
            self._prop_cm = propagate_attributes(**prop_kwargs)
            self._prop_cm.__enter__()
        except Exception:
            self._lf = None
            self._root_cm = None
            self._root_span = None
            self._prop_cm = None
            return self

        tid = getattr(self._root_span, "trace_id", None)
        if tid:
            self._trace_id = str(tid)
        else:
            ctx = getattr(self._root_span, "otel_context", None) or getattr(self._root_span, "_otel_span", None)
            if ctx is not None:
                sc = getattr(ctx, "get_span_context", lambda: None)()
                if sc is not None and getattr(sc, "trace_id", None):
                    self._trace_id = format(sc.trace_id, "032x")
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        try:
            if self._prop_cm is not None:
                self._prop_cm.__exit__(exc_type, exc, tb)
        finally:
            self._prop_cm = None
        try:
            if self._root_cm is not None:
                self._root_cm.__exit__(exc_type, exc, tb)
        finally:
            self._root_cm = None
            self._root_span = None
        if self._lf is not None:
            try:
                self._lf.flush()
            except Exception:
                pass
            self._lf = None

    @contextmanager
    def span(
        self,
        name: str,
        *,
        input_data: Any | None = None,
        metadata: dict[str, Any] | None = None,
        as_type: str = "span",
        model: str | None = None,
    ):
        if self._root_span is None:
            yield None
            return
        meta = _stringify_metadata(metadata or {})
        try:
            # Parent span object: works across threads (run_in_threadpool) unlike OTEL context alone.
            obs_kwargs: dict[str, Any] = {
                "as_type": as_type,
                "name": name,
                "input": input_data,
            }
            if model is not None:
                obs_kwargs["model"] = model
            if meta:
                obs_kwargs["metadata"] = meta
            try:
                child_cm = self._root_span.start_as_current_observation(**obs_kwargs)
            except AttributeError:
                child_cm = self._lf.start_as_current_observation(**obs_kwargs)
            with child_cm as obs:
                yield obs
        finally:
            if self._lf is not None:
                try:
                    self._lf.flush()
                except Exception:
                    pass


def build_safe_llm_output_preview(text: str, *, max_chars: int = 12000) -> str:
    """Truncate model output for Langfuse UI (keep newlines; avoid huge payloads)."""
    s = (text or "").strip()
    if not s:
        return ""
    if len(s) <= max_chars:
        return s
    return f"{s[: max(0, max_chars - 32)]}\n… [truncated, {len(s)} chars total]"


def apply_llm_output_to_langfuse_observation(obs: Any | None, raw_model_text: str) -> None:
    """Set generation `output` so Langfuse UI does not show undefined for the LLM row."""
    if obs is None:
        return
    preview = build_safe_llm_output_preview(raw_model_text)
    if not preview:
        return
    try:
        obs.update(output=preview)
    except Exception:
        pass


def apply_usage_to_langfuse_observation(obs: Any | None, usage: dict[str, int] | None) -> None:
    """Attach token counts to a Langfuse generation observation (SDK v4)."""
    if obs is None or not usage:
        return
    pt = int(usage.get("prompt_tokens") or 0)
    ct = int(usage.get("completion_tokens") or 0)
    tt = int(usage.get("total_tokens") or (pt + ct))
    if pt <= 0 and ct <= 0 and tt <= 0:
        return
    try:
        obs.update(
            usage_details={
                "prompt_tokens": pt,
                "completion_tokens": ct,
                "total_tokens": tt,
            }
        )
    except Exception:
        pass


def build_safe_prompt_preview(prompt: str, *, max_chars: int = 1200) -> str:
    compact = " ".join(prompt.split())
    if len(compact) <= max_chars:
        return compact
    return f"{compact[:max_chars]}..."
