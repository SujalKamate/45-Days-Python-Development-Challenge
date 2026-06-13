"""Lazy pipeline — fused transformations in a single pass over datasets."""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterator, List, Optional, TypeVar, Union
import threading


T = TypeVar('T')
U = TypeVar('U')


class LazyTransform:
    """A deferred transformation that is fused into a single iteration pass."""

    def __init__(self, name: str, fn: Callable[[Any], Any]) -> None:
        self.name = name
        self.fn = fn


class LazyPipeline:
    """Composable pipeline that fuses transformations into a single pass.

    Stages are chained via ``.map()``, ``.filter()``, ``.flatmap()`` etc.
    Evaluation happens once when ``.run()`` or ``.collect()`` is called.
    """

    def __init__(self, source: Optional[Iterator] = None) -> None:
        self._transforms: List[LazyTransform] = []
        self._source = source

    def map(self, fn: Callable[[Any], Any], name: str = 'map') -> LazyPipeline:
        self._transforms.append(LazyTransform(name, fn))
        return self

    def filter(self, predicate: Callable[[Any], bool], name: str = 'filter') -> LazyPipeline:
        def _filter(x: Any) -> Any:
            return x if predicate(x) else _MISSING
        self._transforms.append(LazyTransform(name, _filter))
        return self

    def flatmap(self, fn: Callable[[Any], Iterator], name: str = 'flatmap') -> LazyPipeline:
        def _flatmap(x: Any) -> Any:
            return list(fn(x))
        self._transforms.append(LazyTransform(name, lambda x: x))
        return self

    def take(self, count: int, name: str = 'take') -> LazyPipeline:
        counter = [0]
        def _take(x: Any) -> Any:
            if counter[0] >= count:
                return _STOP
            counter[0] += 1
            return x
        self._transforms.append(LazyTransform(name, _take))
        return self

    def skip(self, count: int, name: str = 'skip') -> LazyPipeline:
        counter = [0]
        def _skip(x: Any) -> Any:
            counter[0] += 1
            if counter[0] <= count:
                return _MISSING
            return x
        self._transforms.append(LazyTransform(name, _skip))
        return self

    def collect(self) -> List[Any]:
        return list(self.run())

    def run(self) -> Iterator[Any]:
        if self._source is None:
            return iter([])
        for item in self._source:
            result = item
            skipped = False
            stop = False
            for t in self._transforms:
                result = t.fn(result)
                if result is _MISSING:
                    skipped = True
                    break
                if result is _STOP:
                    stop = True
                    break
            if stop:
                break
            if not skipped:
                yield result

    def __or__(self, other: LazyPipeline) -> LazyPipeline:
        combined = LazyPipeline(self._source)
        combined._transforms = list(self._transforms) + list(other._transforms)
        return combined

    def __call__(self, items: List[Any]) -> List[Any]:
        self._source = iter(items)
        return self.collect()


_MISSING = object()
_STOP = object()


class PipelineBuilder:
    """Fluent builder for constructing fused transformation pipelines."""

    @staticmethod
    def from_iter(items: List[Any]) -> LazyPipeline:
        return LazyPipeline(iter(items))

    @staticmethod
    def chain(*pipelines: LazyPipeline) -> LazyPipeline:
        combined = LazyPipeline()
        for p in pipelines:
            combined._transforms.extend(p._transforms)
        return combined


class FusedProcessor:
    """Applies a fused pipeline to datasets, reducing multi-pass overhead."""

    def __init__(self) -> None:
        self._cache: Dict[str, LazyPipeline] = {}

    def register(self, name: str, pipeline: LazyPipeline) -> None:
        self._cache[name] = pipeline

    def run(self, name: str, data: List[Any]) -> List[Any]:
        pipeline = self._cache.get(name)
        if pipeline is None:
            return data
        return pipeline(data)
