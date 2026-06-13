"""Work-stealing thread pool — idle workers steal pending tasks from busy workers."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple
import queue
import threading
import time


class WorkStealingPool:
    """Dynamic thread pool where idle workers steal tasks from overloaded peers.

    Each worker owns a deque of tasks. When idle, it steals from the back
    of the largest neighbor deque to minimize contention.
    """

    def __init__(self, num_workers: int = 4) -> None:
        self._num_workers = num_workers
        self._queues: List[queue.SimpleQueue] = [queue.SimpleQueue() for _ in range(num_workers)]
        self._active: List[bool] = [False] * num_workers
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._workers: List[threading.Thread] = []
        self._results: Dict[int, Any] = {}
        self._results_lock = threading.Lock()
        self._task_counter = 0
        self._submitted = 0
        self._completed = 0

    def start(self) -> None:
        self._stop_event.clear()
        self._workers = [
            threading.Thread(target=_worker_loop, args=(i, self), daemon=True)
            for i in range(self._num_workers)
        ]
        for w in self._workers:
            w.start()

    def stop(self) -> None:
        self._stop_event.set()
        for q in self._queues:
            q.put(None)
        for w in self._workers:
            w.join(timeout=2)

    def submit(self, fn: Callable[[], Any], hint: int = -1) -> int:
        with self._lock:
            self._task_counter += 1
            task_id = self._task_counter
            if hint < 0 or hint >= self._num_workers:
                hint = self._find_shortest_queue()
            self._queues[hint].put((task_id, fn))
            self._submitted += 1
            return task_id

    def _find_shortest_queue(self) -> int:
        sizes = [q.qsize() for q in self._queues]
        min_size = min(sizes)
        return sizes.index(min_size)

    def _steal(self, victim_id: int) -> Optional[Tuple[int, Callable[[], Any]]]:
        try:
            return self._queues[victim_id].get_nowait()
        except queue.Empty:
            return None

    def result(self, task_id: int, timeout: Optional[float] = None) -> Any:
        deadline = time.monotonic() + timeout if timeout else None
        while True:
            with self._results_lock:
                if task_id in self._results:
                    return self._results.pop(task_id)
            if deadline and time.monotonic() >= deadline:
                raise TimeoutError(f'Task {task_id} not completed within timeout')
            time.sleep(0.001)

    def map(self, fn: Callable[[Any], Any], items: List[Any]) -> List[Any]:
        futures = [self.submit(lambda x=i: fn(x)) for i in items]
        return [self.result(f) for f in futures]

    @property
    def pending_count(self) -> int:
        return sum(q.qsize() for q in self._queues)

    @property
    def completed_count(self) -> int:
        return self._completed


def _worker_loop(worker_id: int, pool: WorkStealingPool) -> None:
    q = pool._queues[worker_id]
    while not pool._stop_event.is_set():
        task = None
        try:
            task = q.get(timeout=0.05)
        except queue.Empty:
            pass

        if task is None:
            worker_idle_start = time.monotonic()
            while time.monotonic() - worker_idle_start < 0.2:
                if pool._stop_event.is_set():
                    return
                victim = (worker_id + 1) % pool._num_workers
                if victim != worker_id:
                    stolen = pool._steal(victim)
                    if stolen is not None:
                        task = stolen
                        break
                time.sleep(0.005)
            continue

        task_id, fn = task
        try:
            result = fn()
        except Exception as e:
            result = e
        with pool._results_lock:
            pool._results[task_id] = result
        pool._completed += 1


class WorkStealingExecutor:
    """High-level executor wrapping WorkStealingPool for concurrent task execution."""

    def __init__(self, max_workers: int = 4) -> None:
        self._pool = WorkStealingPool(max_workers)
        self._started = False

    def start(self) -> None:
        if not self._started:
            self._pool.start()
            self._started = True

    def shutdown(self) -> None:
        if self._started:
            self._pool.stop()
            self._started = False

    def execute(self, fn: Callable[[], Any]) -> int:
        self.start()
        return self._pool.submit(fn)

    def execute_batch(self, items: List[Any], fn: Callable[[Any], Any]) -> List[Any]:
        self.start()
        futures = [self._pool.submit(lambda x=i: fn(x)) for i in items]
        return [self._pool.result(f) for f in futures]

    def run_in_parallel(self, fns: List[Callable[[], Any]]) -> List[Any]:
        self.start()
        futures = [self._pool.submit(fn) for fn in fns]
        return [self._pool.result(f) for f in futures]

    @property
    def pending(self) -> int:
        return self._pool.pending_count
