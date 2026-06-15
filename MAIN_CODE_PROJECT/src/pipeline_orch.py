"""Declarative multi-module pipeline composition and DAG-based workflow orchestration."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import datetime
import json
import os
import threading
import time
import uuid


class PipelineStep:
    """A single step in a pipeline DAG."""

    def __init__(self, step_id: str, label: str = '',
                 fn: Optional[Callable[..., Any]] = None,
                 depends_on: Optional[List[str]] = None,
                 condition: Optional[str] = '',
                 parallel: bool = False,
                 timeout_s: float = 0,
                 retry: int = 1,
                 args: Optional[List[Any]] = None,
                 kwargs: Optional[Dict[str, Any]] = None) -> None:
        self.id = step_id
        self.label = label or step_id
        self.fn = fn
        self.depends_on = depends_on or []
        self.condition = condition
        self.parallel = parallel
        self.timeout_s = timeout_s
        self.retry = retry
        self.args = args or []
        self.kwargs = kwargs or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'label': self.label,
            'depends_on': self.depends_on,
            'condition': self.condition,
            'parallel': self.parallel,
            'timeout_s': self.timeout_s,
            'retry': self.retry,
        }


class StepResult:
    """Result of executing a single pipeline step."""

    def __init__(self, step_id: str, status: str = 'pending',
                 result: Any = None, error: str = '',
                 elapsed_s: float = 0.0, attempt: int = 0) -> None:
        self.step_id = step_id
        self.status = status
        self.result = result
        self.error = error
        self.elapsed_s = elapsed_s
        self.attempt = attempt
        self.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'step_id': self.step_id,
            'status': self.status,
            'result': repr(self.result)[:200] if self.result is not None else None,
            'error': self.error[:500] if self.error else '',
            'elapsed_s': round(self.elapsed_s, 4),
            'attempt': self.attempt,
            'timestamp': self.timestamp,
        }


class PipelineDAG:
    """Directed acyclic graph with topological sort and cycle detection."""

    def __init__(self) -> None:
        self._steps: Dict[str, PipelineStep] = {}

    def add_step(self, step: PipelineStep) -> None:
        self._steps[step.id] = step

    def get_step(self, step_id: str) -> Optional[PipelineStep]:
        return self._steps.get(step_id)

    def steps(self) -> Dict[str, PipelineStep]:
        return self._steps

    def topological_sort(self) -> List[PipelineStep]:
        in_degree: Dict[str, int] = {}
        adj: Dict[str, List[str]] = {}

        for sid, step in self._steps.items():
            in_degree.setdefault(sid, 0)
            adj.setdefault(sid, [])
            for dep in step.depends_on:
                adj.setdefault(dep, [])
                adj[dep].append(sid)
                in_degree[sid] = in_degree.get(sid, 0) + 1

        queue: List[str] = [sid for sid, deg in in_degree.items() if deg == 0]
        sorted_steps: List[PipelineStep] = []

        while queue:
            sid = queue.pop(0)
            if sid in self._steps:
                sorted_steps.append(self._steps[sid])
            for neighbor in adj.get(sid, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_steps) != len(self._steps):
            raise ValueError('Cycle detected in pipeline DAG')

        return sorted_steps

    def detect_cycles(self) -> List[str]:
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        cycle_nodes: List[str] = []

        def dfs(sid: str) -> bool:
            visited.add(sid)
            rec_stack.add(sid)
            for dep in self._steps.get(sid, PipelineStep('')).depends_on:
                if dep not in visited:
                    if dfs(dep):
                        return True
                elif dep in rec_stack:
                    cycle_nodes.append(sid)
                    return True
            rec_stack.discard(sid)
            return False

        for sid in self._steps:
            if sid not in visited:
                dfs(sid)
        return cycle_nodes

    def parallel_groups(self) -> List[List[PipelineStep]]:
        sorted_steps = self.topological_sort()
        groups: List[List[PipelineStep]] = []
        current_group: List[PipelineStep] = []
        for step in sorted_steps:
            if step.parallel:
                current_group.append(step)
            else:
                if current_group:
                    groups.append(current_group)
                    current_group = []
                groups.append([step])
        if current_group:
            groups.append(current_group)
        return groups


class PipelineConfig:
    """Load pipeline definitions from YAML/JSON dict."""

    @staticmethod
    def from_dict(data: Dict[str, Any], registry: Dict[str, Callable[..., Any]]) -> PipelineDAG:
        dag = PipelineDAG()
        for item in data.get('steps', []):
            sid = item.get('id', uuid.uuid4().hex[:8])
            fn_name = item.get('fn', '')
            fn = registry.get(fn_name)
            step = PipelineStep(
                step_id=sid,
                label=item.get('label', sid),
                fn=fn,
                depends_on=item.get('depends_on', []),
                condition=item.get('condition', ''),
                parallel=item.get('parallel', False),
                timeout_s=item.get('timeout_s', 0),
                retry=item.get('retry', 1),
            )
            dag.add_step(step)
        cycles = dag.detect_cycles()
        if cycles:
            raise ValueError(f'Cycle detected involving steps: {cycles}')
        return dag


class PipelineExecutor:
    """Execute a pipeline DAG respecting dependencies, conditions, and parallelism."""

    def __init__(self) -> None:
        self._results: Dict[str, StepResult] = {}
        self._lock = threading.Lock()

    def execute(self, dag: PipelineDAG,
                context: Optional[Dict[str, Any]] = None) -> Dict[str, StepResult]:
        ctx = context or {}
        parallel_groups = dag.parallel_groups()

        for group in parallel_groups:
            if len(group) == 1:
                self._execute_step(group[0], ctx)
            else:
                threads = []
                for step in group:
                    t = threading.Thread(target=self._execute_step, args=(step, ctx))
                    t.start()
                    threads.append(t)
                for t in threads:
                    t.join()

        return dict(self._results)

    def _execute_step(self, step: PipelineStep, context: Dict[str, Any]) -> None:
        if step.condition:
            if not self._evaluate_condition(step.condition, context):
                result = StepResult(step.id, 'skipped', result=None)
                with self._lock:
                    self._results[step.id] = result
                return

        for dep_id in step.depends_on:
            dep_result = self._results.get(dep_id)
            if dep_result and dep_result.status == 'error':
                result = StepResult(step.id, 'skipped_dependency',
                                    error=f'Dependency {dep_id} failed')
                with self._lock:
                    self._results[step.id] = result
                return

        last_exc: Optional[Exception] = None
        for attempt in range(1, step.retry + 1):
            start = time.perf_counter()
            try:
                if step.fn:
                    result_val = step.fn(*step.args, **step.kwargs)
                else:
                    result_val = None
                elapsed = time.perf_counter() - start
                result = StepResult(step.id, 'completed', result_val, elapsed_s=elapsed, attempt=attempt)
                with self._lock:
                    self._results[step.id] = result
                return
            except Exception as e:
                elapsed = time.perf_counter() - start
                last_exc = e
                if attempt < step.retry:
                    time.sleep(0.5 * attempt)

        result = StepResult(step.id, 'error', error=str(last_exc or ''),
                            elapsed_s=0.0, attempt=step.retry)
        with self._lock:
            self._results[step.id] = result

    @staticmethod
    def _evaluate_condition(condition: str, context: Dict[str, Any]) -> bool:
        try:
            return bool(eval(condition, {'__builtins__': {}}, context))
        except Exception:
            return True


class PipelineRunRecord:
    """Record of a completed pipeline execution."""

    def __init__(self, name: str, dag: PipelineDAG,
                 results: Dict[str, StepResult]) -> None:
        self.run_id = uuid.uuid4().hex[:12]
        self.name = name
        self.results = results
        self.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def summary(self) -> Dict[str, Any]:
        total = len(self.results)
        completed = sum(1 for r in self.results.values() if r.status == 'completed')
        skipped = sum(1 for r in self.results.values() if r.status in ('skipped', 'skipped_dependency'))
        errors = sum(1 for r in self.results.values() if r.status == 'error')
        total_time = sum(r.elapsed_s for r in self.results.values())
        return {
            'run_id': self.run_id,
            'name': self.name,
            'total_steps': total,
            'completed': completed,
            'skipped': skipped,
            'errors': errors,
            'total_time_s': round(total_time, 4),
            'timestamp': self.timestamp,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            'run_id': self.run_id,
            'name': self.name,
            'steps': {k: v.to_dict() for k, v in self.results.items()},
            'summary': self.summary(),
            'timestamp': self.timestamp,
        }


class PipelineOrchestrator:
    """Top-level pipeline workflow orchestrator."""

    def __init__(self) -> None:
        self._registry: Dict[str, Callable[..., Any]] = {}
        self._executor = PipelineExecutor()
        self._runs: List[PipelineRunRecord] = []
        self._lock = threading.Lock()

    def register_step_fn(self, name: str, fn: Callable[..., Any]) -> None:
        self._registry[name] = fn

    def unregister_step_fn(self, name: str) -> bool:
        return self._registry.pop(name, None) is not None

    def list_step_fns(self) -> List[str]:
        return list(self._registry.keys())

    def from_dict(self, data: Dict[str, Any]) -> PipelineDAG:
        return PipelineConfig.from_dict(data, self._registry)

    def from_json(self, path: str) -> PipelineDAG:
        with open(path, 'r') as f:
            data = json.load(f)
        return self.from_dict(data)

    def execute(self, dag: PipelineDAG, name: str = '',
                context: Optional[Dict[str, Any]] = None) -> PipelineRunRecord:
        results = self._executor.execute(dag, context)
        record = PipelineRunRecord(name or 'unnamed', dag, results)
        with self._lock:
            self._runs.append(record)
        return record

    def run_from_dict(self, data: Dict[str, Any], name: str = '',
                      context: Optional[Dict[str, Any]] = None) -> PipelineRunRecord:
        dag = self.from_dict(data)
        return self.execute(dag, name, context)

    def run_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return [r.to_dict() for r in self._runs[-limit:]]

    def run_summary(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            for r in self._runs:
                if r.run_id == run_id:
                    return r.to_dict()
        return None

    def last_run(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            if self._runs:
                return self._runs[-1].to_dict()
        return None

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            total_runs = len(self._runs)
            total_steps = sum(len(r.results) for r in self._runs)
            total_errors = sum(
                sum(1 for r in run.results.values() if r.status == 'error')
                for run in self._runs
            )
        return {
            'registered_fns': len(self._registry),
            'total_runs': total_runs,
            'total_steps': total_steps,
            'total_errors': total_errors,
        }

    def report_text(self) -> str:
        s = self.summary()
        return (
            f'Pipeline Orchestrator\n'
            f'  Registered step functions: {s["registered_fns"]}\n'
            f'  Total runs: {s["total_runs"]}\n'
            f'  Total steps: {s["total_steps"]}\n'
            f'  Total errors: {s["total_errors"]}'
        )

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        sp = os.path.join(dir, 'pipeline_orch.json')
        with open(sp, 'w') as f:
            json.dump(self.summary(), f, indent=2)
        paths.append(sp)
        hp = os.path.join(dir, 'pipeline_runs.json')
        with open(hp, 'w') as f:
            json.dump(self.run_history(limit=500), f, indent=2)
        paths.append(hp)
        return paths
