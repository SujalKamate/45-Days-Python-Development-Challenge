"""Algebraic effects and structured error handling framework."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple, Type
import datetime
import json
import os
import threading
import time
import uuid


class Effect:
    """A typed effect declaration representing an operation that may fail."""

    def __init__(self, effect_type: str, payload: Any = None,
                 metadata: Optional[Dict[str, Any]] = None) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.effect_type = effect_type
        self.payload = payload
        self.metadata = metadata or {}
        self.created_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'effect_type': self.effect_type,
            'payload': str(self.payload)[:200],
            'metadata': self.metadata,
        }


class EffectResult:
    """Result of handling an effect."""

    def __init__(self, effect: Effect, handled: bool = False,
                 value: Any = None, action: str = 'resume',
                 error: Optional[str] = None) -> None:
        self.effect = effect
        self.handled = handled
        self.value = value
        self.action = action
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            'effect_id': self.effect.id,
            'effect_type': self.effect.effect_type,
            'handled': self.handled,
            'action': self.action,
            'value': str(self.value)[:200] if self.value else None,
            'error': self.error,
        }


class EffectHandler:
    """Handles a specific effect type with configurable resolution strategy."""

    def __init__(self, effect_type: str,
                 handler_fn: Optional[Callable[[Effect], EffectResult]] = None) -> None:
        self.effect_type = effect_type
        self._handler_fn = handler_fn
        self._handled_count = 0

    def can_handle(self, effect: Effect) -> bool:
        return effect.effect_type == self.effect_type

    def handle(self, effect: Effect) -> EffectResult:
        if self._handler_fn:
            result = self._handler_fn(effect)
        else:
            result = EffectResult(effect, handled=True, value=None)
        self._handled_count += 1
        return result

    @property
    def handled_count(self) -> int:
        return self._handled_count


class IOEffect(Effect):
    """Effect for I/O operations."""

    def __init__(self, operation: str, path: str = '',
                 data: Any = None) -> None:
        super().__init__('io', {'operation': operation, 'path': path, 'data': str(data)[:200]})
        self.operation = operation
        self.path = path
        self.data = data


class TimeoutEffect(Effect):
    """Effect for timeout monitoring."""

    def __init__(self, duration_s: float, context: str = '') -> None:
        super().__init__('timeout', {'duration_s': duration_s, 'context': context})
        self.duration_s = duration_s
        self.context = context


class ValidationEffect(Effect):
    """Effect for validation failures."""

    def __init__(self, field: str, value: Any, reason: str = '') -> None:
        super().__init__('validation', {'field': field, 'value': str(value)[:200], 'reason': reason})
        self.field = field
        self.value = value
        self.reason = reason


class EffectComposition:
    """Hierarchical composition of effect handlers."""

    def __init__(self) -> None:
        self._handlers: List[EffectHandler] = []
        self._fallback: Optional[EffectHandler] = None

    def add_handler(self, handler: EffectHandler) -> None:
        self._handlers.append(handler)

    def set_fallback(self, handler: EffectHandler) -> None:
        self._fallback = handler

    def resolve(self, effect: Effect) -> EffectResult:
        for handler in self._handlers:
            if handler.can_handle(effect):
                return handler.handle(effect)
        if self._fallback:
            return self._fallback.handle(effect)
        return EffectResult(effect, handled=False, action='abort',
                            error=f'No handler for {effect.effect_type}')

    def remove_handler(self, effect_type: str) -> bool:
        for i, h in enumerate(self._handlers):
            if h.effect_type == effect_type:
                self._handlers.pop(i)
                return True
        return False

    def summary(self) -> Dict[str, Any]:
        return {
            'handler_count': len(self._handlers),
            'handler_types': [h.effect_type for h in self._handlers],
            'has_fallback': self._fallback is not None,
        }


class EffectProcessor:
    """Coroutine-based effect processing with generator suspension."""

    def __init__(self, composition: EffectComposition) -> None:
        self._composition = composition
        self._processing_history: List[Dict[str, Any]] = []

    def process(self, generator_fn: Callable[..., Any],
                *args: Any, **kwargs: Any) -> Any:
        gen = generator_fn(*args, **kwargs)
        if not hasattr(gen, 'send'):
            return gen

        value = None
        exc: Optional[Exception] = None

        while True:
            try:
                if exc:
                    result = gen.throw(exc)
                    exc = None
                else:
                    result = gen.send(value)
            except StopIteration as e:
                return e.value

            if isinstance(result, Effect):
                effect_result = self._composition.resolve(result)
                self._processing_history.append({
                    'effect': result.to_dict(),
                    'result': effect_result.to_dict(),
                    'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                })

                if effect_result.action == 'abort':
                    raise RuntimeError(
                        f'Effect aborted: {result.effect_type}: {effect_result.error}'
                    )
                if effect_result.action == 'retry':
                    value = effect_result
                    continue
                if effect_result.action == 'resume':
                    value = effect_result.value
                else:
                    value = effect_result.value
            else:
                value = result

    def history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._processing_history[-limit:]


class AlgebraicEffectsEngine:
    """Top-level algebraic effects framework."""

    def __init__(self) -> None:
        self._composition = EffectComposition()
        self._processor = EffectProcessor(self._composition)
        self._lock = threading.Lock()
        self._total_effects = 0
        self._handled_effects = 0

    @property
    def composition(self) -> EffectComposition:
        return self._composition

    @property
    def processor(self) -> EffectProcessor:
        return self._processor

    def register_handler(self, effect_type: str,
                         handler_fn: Optional[Callable[[Effect], EffectResult]] = None,
                         handler: Optional[EffectHandler] = None) -> None:
        if handler:
            self._composition.add_handler(handler)
        else:
            self._composition.add_handler(EffectHandler(effect_type, handler_fn))

    def effect(self, effect_type: str, payload: Any = None,
               metadata: Optional[Dict[str, Any]] = None) -> Effect:
        with self._lock:
            self._total_effects += 1
        return Effect(effect_type, payload, metadata)

    def io_effect(self, operation: str, path: str = '',
                  data: Any = None) -> IOEffect:
        return IOEffect(operation, path, data)

    def timeout_effect(self, duration_s: float, context: str = '') -> TimeoutEffect:
        return TimeoutEffect(duration_s, context)

    def validation_effect(self, field: str, value: Any,
                          reason: str = '') -> ValidationEffect:
        return ValidationEffect(field, value, reason)

    def process(self, gen_fn: Callable[..., Any],
                *args: Any, **kwargs: Any) -> Any:
        result = self._processor.process(gen_fn, *args, **kwargs)
        with self._lock:
            self._handled_effects = self._composition.summary()['handler_count']
        return result

    def handler_summary(self) -> Dict[str, Any]:
        return self._composition.summary()

    def summary(self) -> Dict[str, Any]:
        return {
            'handlers': self._composition.summary(),
            'total_effects': self._total_effects,
        }

    def report_text(self) -> str:
        s = self.summary()
        h = s['handlers']
        return (
            f'Algebraic Effects Engine\n'
            f'  Handlers: {h["handler_count"]} ({", ".join(h["handler_types"])})\n'
            f'  Total effects: {s["total_effects"]}'
        )

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        sp = os.path.join(dir, 'algebraic_effects.json')
        with open(sp, 'w') as f:
            json.dump(self.summary(), f, indent=2)
        paths.append(sp)
        hp = os.path.join(dir, 'effect_processing.json')
        with open(hp, 'w') as f:
            json.dump(self._processor.history(200), f, indent=2)
        paths.append(hp)
        return paths
