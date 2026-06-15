"""Distributed tracing with OpenTelemetry-compatible spans, context propagation, and export."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple
import datetime
import json
import os
import random
import threading
import time
import uuid


_TRACE_PARENT_KEY = 'traceparent'
_TRACESTATE_KEY = 'tracestate'
_SAMPLING_RATE = 1.0


def _generate_id(nbytes: int = 8) -> str:
    return uuid.uuid4().hex[:nbytes * 2]


def _now_ns() -> int:
    return time.time_ns()


class SpanContext:
    """W3C Trace Context for a span."""

    def __init__(self, trace_id: str, span_id: str, is_remote: bool = False, trace_flags: int = 1) -> None:
        self.trace_id = trace_id
        self.span_id = span_id
        self.is_remote = is_remote
        self.trace_flags = trace_flags

    def to_traceparent(self) -> str:
        return f'00-{self.trace_id}-{self.span_id}-{"01" if self.trace_flags & 1 else "00"}'

    @staticmethod
    def from_traceparent(tp: str) -> Optional[SpanContext]:
        parts = tp.strip().split('-')
        if len(parts) == 4:
            return SpanContext(parts[1], parts[2], is_remote=True, trace_flags=int(parts[3], 16))
        return None


class Span:
    """A single trace span with timing, attributes, and events."""

    def __init__(self, name: str, context: SpanContext, parent_span_id: Optional[str] = None,
                 kind: str = 'INTERNAL') -> None:
        self.name = name
        self.context = context
        self.parent_span_id = parent_span_id
        self.kind = kind
        self.start_time = _now_ns()
        self.end_time: Optional[int] = None
        self.attributes: Dict[str, Any] = {}
        self.events: List[Dict[str, Any]] = []
        self.status: Optional[str] = None
        self._ended = False

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        self.events.append({
            'name': name,
            'timestamp': _now_ns(),
            'attributes': attributes or {},
        })

    def set_status(self, status: str) -> None:
        self.status = status

    def end(self) -> None:
        if not self._ended:
            self.end_time = _now_ns()
            self._ended = True

    @property
    def duration_ns(self) -> int:
        if self.end_time:
            return self.end_time - self.start_time
        return _now_ns() - self.start_time

    @property
    def duration_ms(self) -> float:
        return self.duration_ns / 1_000_000

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'trace_id': self.context.trace_id,
            'span_id': self.context.span_id,
            'parent_span_id': self.parent_span_id or '',
            'kind': self.kind,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration_ns': self.duration_ns,
            'attributes': self.attributes,
            'events': self.events,
            'status': self.status or 'UNSET',
        }


class Tracer:
    """Creates and manages spans with context propagation."""

    def __init__(self, name: str = 'application') -> None:
        self._name = name
        self._active_span: Optional[Span] = None
        self._lock = threading.Lock()
        self._current_trace_id: Optional[str] = None

    def start_span(self, name: str, kind: str = 'INTERNAL',
                   attributes: Optional[Dict[str, Any]] = None,
                   parent: Optional[Span] = None) -> Span:
        trace_id = self._current_trace_id or _generate_id(16)
        span_id = _generate_id(8)
        parent_span_id = None
        if parent:
            trace_id = parent.context.trace_id
            parent_span_id = parent.context.span_id
        elif self._active_span:
            trace_id = self._active_span.context.trace_id
            parent_span_id = self._active_span.context.span_id

        ctx = SpanContext(trace_id, span_id)
        span = Span(name, ctx, parent_span_id, kind)
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, v)

        with self._lock:
            self._active_span = span
            self._current_trace_id = trace_id
        return span

    def end_span(self, span: Span, status: str = 'OK') -> None:
        span.set_status(status)
        span.end()
        with self._lock:
            if self._active_span and self._active_span.context.span_id == span.context.span_id:
                self._active_span = None

    def trace(self, name: str, kind: str = 'INTERNAL',
              attributes: Optional[Dict[str, Any]] = None) -> '_SpanContextManager':
        return _SpanContextManager(self, name, kind, attributes)

    def inject(self, headers: Dict[str, str], span: Optional[Span] = None) -> Dict[str, str]:
        s = span or self._active_span
        if s:
            headers[_TRACE_PARENT_KEY] = s.context.to_traceparent()
        return headers

    def extract(self, headers: Dict[str, str]) -> Optional[SpanContext]:
        tp = headers.get(_TRACE_PARENT_KEY)
        if tp:
            ctx = SpanContext.from_traceparent(tp)
            if ctx:
                self._current_trace_id = ctx.trace_id
                return ctx
        return None

    @property
    def active_span(self) -> Optional[Span]:
        with self._lock:
            return self._active_span


class _SpanContextManager:
    """Context manager for tracing spans."""

    def __init__(self, tracer: Tracer, name: str, kind: str, attributes: Optional[Dict[str, Any]]) -> None:
        self._tracer = tracer
        self._name = name
        self._kind = kind
        self._attributes = attributes
        self._span: Optional[Span] = None

    def __enter__(self) -> Span:
        self._span = self._tracer.start_span(self._name, self._kind, self._attributes)
        return self._span

    def __exit__(self, *args: Any) -> None:
        if self._span:
            self._tracer.end_span(self._span)


class Sampler:
    """Trace sampling policy."""

    def __init__(self, rate: float = _SAMPLING_RATE) -> None:
        self._rate = rate
        self._rng = random.Random()

    def should_sample(self, trace_id: Optional[str] = None) -> bool:
        return self._rng.random() < self._rate

    @property
    def rate(self) -> float:
        return self._rate

    def set_rate(self, rate: float) -> None:
        self._rate = max(0.0, min(1.0, rate))


class SpanExporter:
    """Exports spans to a collector or storage."""

    def __init__(self, endpoint: str = '') -> None:
        self._endpoint = endpoint
        self._buffer: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def export(self, span: Span) -> None:
        with self._lock:
            self._buffer.append(span.to_dict())

    def export_batch(self, spans: List[Span]) -> None:
        with self._lock:
            self._buffer.extend(s.to_dict() for s in spans)

    def flush(self) -> List[Dict[str, Any]]:
        with self._lock:
            batch = list(self._buffer)
            self._buffer.clear()
        return batch

    def export_to_json(self, path: str) -> None:
        data = self.flush()
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, default=str)

    @property
    def buffer_size(self) -> int:
        with self._lock:
            return len(self._buffer)


class TracerProvider:
    """Provides tracer instances and manages export."""

    def __init__(self, sampler: Optional[Sampler] = None, exporter: Optional[SpanExporter] = None) -> None:
        self._sampler = sampler or Sampler()
        self._exporter = exporter or SpanExporter()
        self._tracers: Dict[str, Tracer] = {}
        self._lock = threading.Lock()

    def get_tracer(self, name: str = 'application') -> Tracer:
        with self._lock:
            if name not in self._tracers:
                self._tracers[name] = Tracer(name)
            return self._tracers[name]

    @property
    def sampler(self) -> Sampler:
        return self._sampler

    @property
    def exporter(self) -> SpanExporter:
        return self._exporter

    def flush_all(self) -> List[Dict[str, Any]]:
        return self._exporter.flush()

    def export_all(self, path: str) -> None:
        self._exporter.export_to_json(path)


class TraceContextPropagator:
    """Propagates trace context via headers for distributed workflows."""

    @staticmethod
    def inject(context: SpanContext, carrier: Dict[str, str]) -> Dict[str, str]:
        carrier[_TRACE_PARENT_KEY] = context.to_traceparent()
        return carrier

    @staticmethod
    def extract(carrier: Dict[str, str]) -> Optional[SpanContext]:
        return SpanContext.from_traceparent(carrier.get(_TRACE_PARENT_KEY, ''))


class DistributedTracer:
    """Top-level distributed tracing interface."""

    def __init__(self, service_name: str = 'app', sampling_rate: float = 1.0) -> None:
        self._service = service_name
        self._provider = TracerProvider(Sampler(sampling_rate))
        self._tracer = self._provider.get_tracer(service_name)
        self._propagator = TraceContextPropagator()

    @property
    def tracer(self) -> Tracer:
        return self._tracer

    @property
    def provider(self) -> TracerProvider:
        return self._provider

    def start_span(self, name: str, kind: str = 'INTERNAL',
                   attributes: Optional[Dict[str, Any]] = None) -> Span:
        return self._tracer.start_span(name, kind, attributes)

    def end_span(self, span: Span, status: str = 'OK') -> None:
        self._tracer.end_span(span, status)

    def trace(self, name: str, kind: str = 'INTERNAL',
              attributes: Optional[Dict[str, Any]] = None) -> _SpanContextManager:
        return self._tracer.trace(name, kind, attributes)

    def inject(self, headers: Dict[str, str], span: Optional[Span] = None) -> Dict[str, str]:
        return self._tracer.inject(headers, span)

    def extract(self, headers: Dict[str, str]) -> Optional[SpanContext]:
        return self._tracer.extract(headers)

    def set_sampling_rate(self, rate: float) -> None:
        self._provider.sampler.set_rate(rate)

    def export(self, path: str) -> None:
        self._provider.export_all(path)

    def flush(self) -> List[Dict[str, Any]]:
        return self._provider.flush_all()

    def summary(self) -> Dict[str, Any]:
        spans = self._provider.exporter.buffer_size
        return {
            'service': self._service,
            'sampling_rate': self._provider.sampler.rate,
            'buffered_spans': spans,
        }

    def report_text(self) -> str:
        s = self.summary()
        return (
            f'Distributed Tracing Report\n'
            f'  Service: {s["service"]}\n'
            f'  Sampling rate: {s["sampling_rate"]}\n'
            f'  Buffered spans: {s["buffered_spans"]}'
        )

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        ep = os.path.join(dir, 'traces.json')
        self.export(ep)
        paths.append(ep)
        return paths
