"""GraphQL subscription support for real-time module progress monitoring and event streaming."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import datetime
import json
import os
import queue
import threading
import time
import uuid


_SUBSCRIBER_TIMEOUT_S = 30.0
_EVENT_BATCH_SIZE = 100
_MAX_SUBSCRIBERS = 1000


class GraphQLEvent:
    """A single event published to subscribers."""

    def __init__(self, topic: str, event_type: str, data: Any,
                 module: str = '', metadata: Optional[Dict[str, Any]] = None) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.topic = topic
        self.event_type = event_type
        self.data = data
        self.module = module
        self.metadata = metadata or {}
        self.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'topic': self.topic,
            'event_type': self.event_type,
            'data': self.data,
            'module': self.module,
            'metadata': self.metadata,
            'timestamp': self.timestamp,
        }


class SubscriptionFilter:
    """Filter criteria for subscription events."""

    def __init__(self, topics: Optional[List[str]] = None,
                 event_types: Optional[List[str]] = None,
                 modules: Optional[List[str]] = None) -> None:
        self.topics = set(topics) if topics else None
        self.event_types = set(event_types) if event_types else None
        self.modules = set(modules) if modules else None

    def matches(self, event: GraphQLEvent) -> bool:
        if self.topics and event.topic not in self.topics:
            return False
        if self.event_types and event.event_type not in self.event_types:
            return False
        if self.modules and event.module not in self.modules:
            return False
        return True


class Subscriber:
    """A single subscription with its event queue."""

    def __init__(self, sub_id: str, filter: SubscriptionFilter,
                 callback: Optional[Callable[[GraphQLEvent], None]] = None) -> None:
        self.id = sub_id
        self.filter = filter
        self.callback = callback
        self._queue: queue.Queue = queue.Queue(maxsize=1000)
        self._active = True
        self._created_at = time.time()
        self._last_poll = time.time()

    def push(self, event: GraphQLEvent) -> bool:
        if not self._active:
            return False
        if not self.filter.matches(event):
            return False
        try:
            self._queue.put_nowait(event)
            if self.callback:
                try:
                    self.callback(event)
                except Exception:
                    pass
            return True
        except queue.Full:
            return False

    def poll(self, timeout: float = 1.0) -> Optional[GraphQLEvent]:
        try:
            event = self._queue.get(timeout=timeout)
            self._last_poll = time.time()
            return event
        except queue.Empty:
            return None

    def poll_batch(self, max_events: int = 10, timeout: float = 0.5) -> List[GraphQLEvent]:
        events = []
        deadline = time.time() + timeout
        while len(events) < max_events and time.time() < deadline:
            event = self.poll(timeout=0.05)
            if event:
                events.append(event)
            else:
                break
        return events

    @property
    def active(self) -> bool:
        return self._active

    def deactivate(self) -> None:
        self._active = False

    @property
    def is_stale(self, timeout: float = _SUBSCRIBER_TIMEOUT_S) -> bool:
        return (time.time() - self._last_poll) > timeout

    @property
    def pending_count(self) -> int:
        return self._queue.qsize()


class SubscriptionManager:
    """Manages subscribers, topics, and event dispatch."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, Subscriber] = {}
        self._topic_subscribers: Dict[str, Set[str]] = {}
        self._lock = threading.Lock()
        self._event_count = 0
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()

    def subscribe(self, filter: SubscriptionFilter,
                  callback: Optional[Callable[[GraphQLEvent], None]] = None) -> str:
        sub_id = uuid.uuid4().hex[:16]
        sub = Subscriber(sub_id, filter, callback)
        with self._lock:
            self._subscribers[sub_id] = sub
            if filter.topics:
                for t in filter.topics:
                    if t not in self._topic_subscribers:
                        self._topic_subscribers[t] = set()
                    self._topic_subscribers[t].add(sub_id)
        return sub_id

    def unsubscribe(self, sub_id: str) -> bool:
        with self._lock:
            sub = self._subscribers.pop(sub_id, None)
            if sub is None:
                return False
            for topic_subs in self._topic_subscribers.values():
                topic_subs.discard(sub_id)
            sub.deactivate()
        return True

    def publish(self, event: GraphQLEvent) -> int:
        delivered = 0
        with self._lock:
            topic_subs = self._topic_subscribers.get(event.topic, set())
            for sub_id in topic_subs:
                sub = self._subscribers.get(sub_id)
                if sub and sub.push(event):
                    delivered += 1
        self._event_count += 1
        return delivered

    def publish_batch(self, events: List[GraphQLEvent]) -> int:
        return sum(self.publish(e) for e in events)

    def get_subscriber(self, sub_id: str) -> Optional[Subscriber]:
        with self._lock:
            return self._subscribers.get(sub_id)

    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)

    def _cleanup_loop(self) -> None:
        while True:
            time.sleep(10)
            stale = []
            with self._lock:
                for sid, sub in self._subscribers.items():
                    if sub.is_stale:
                        stale.append(sid)
                for sid in stale:
                    self._subscribers.pop(sid, None)
                    for t in self._topic_subscribers.values():
                        t.discard(sid)


class GraphQLSubscriptionServer:
    """SSE-based GraphQL subscription streaming server."""

    def __init__(self, manager: SubscriptionManager, host: str = '0.0.0.0', port: int = 8900) -> None:
        self._manager = manager
        self._host = host
        self._port = port
        self._server: Optional[Any] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        import http.server
        mgr = self._manager

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path.startswith('/subscribe'):
                    from urllib.parse import urlparse, parse_qs
                    qs = parse_qs(urlparse(self.path).query)
                    topics = qs.get('topics', ['*'])
                    event_types = qs.get('eventTypes', ['*'])
                    sub_id = mgr.subscribe(SubscriptionFilter(
                        topics=None if topics == ['*'] else topics,
                        event_types=None if event_types == ['*'] else event_types,
                    ))
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/event-stream')
                    self.send_header('Cache-Control', 'no-cache')
                    self.send_header('Connection', 'keep-alive')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(f'event: connected\ndata: {json.dumps({"subscriptionId": sub_id})}\n\n'.encode())
                    sub = mgr.get_subscriber(sub_id)
                    while sub and sub.active:
                        events = sub.poll_batch(timeout=1.0)
                        for ev in events:
                            self.wfile.write(f'event: {ev.event_type}\ndata: {json.dumps(ev.to_dict())}\n\n'.encode())
                            self.wfile.flush()
                        if not sub.active:
                            break
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, fmt, *args):
                pass

        self._server = http.server.HTTPServer((self._host, self._port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()


class GraphQLSubscriptionEngine:
    """Top-level GraphQL subscription engine for real-time event streaming."""

    def __init__(self) -> None:
        self._manager = SubscriptionManager()
        self._server: Optional[GraphQLSubscriptionServer] = None

    @property
    def manager(self) -> SubscriptionManager:
        return self._manager

    def publish(self, topic: str, event_type: str, data: Any,
                module: str = '', metadata: Optional[Dict[str, Any]] = None) -> GraphQLEvent:
        event = GraphQLEvent(topic, event_type, data, module, metadata)
        self._manager.publish(event)
        return event

    def publish_batch(self, events: List[GraphQLEvent]) -> int:
        return self._manager.publish_batch(events)

    def subscribe(self, topics: Optional[List[str]] = None,
                  event_types: Optional[List[str]] = None,
                  modules: Optional[List[str]] = None,
                  callback: Optional[Callable[[GraphQLEvent], None]] = None) -> str:
        return self._manager.subscribe(
            SubscriptionFilter(topics, event_types, modules), callback
        )

    def unsubscribe(self, sub_id: str) -> bool:
        return self._manager.unsubscribe(sub_id)

    def poll(self, sub_id: str, timeout: float = 1.0) -> Optional[GraphQLEvent]:
        sub = self._manager.get_subscriber(sub_id)
        if sub:
            return sub.poll(timeout)
        return None

    def poll_batch(self, sub_id: str, max_events: int = 10, timeout: float = 0.5) -> List[GraphQLEvent]:
        sub = self._manager.get_subscriber(sub_id)
        if sub:
            return sub.poll_batch(max_events, timeout)
        return []

    def start_sse_server(self, host: str = '0.0.0.0', port: int = 8900) -> GraphQLSubscriptionServer:
        self._server = GraphQLSubscriptionServer(self._manager, host, port)
        self._server.start()
        return self._server

    def stop_server(self) -> None:
        if self._server:
            self._server.stop()

    def subscriber_count(self) -> int:
        return self._manager.subscriber_count()

    def event_count(self) -> int:
        return self._manager._event_count

    def summary(self) -> Dict[str, Any]:
        return {
            'active_subscribers': self.subscriber_count(),
            'total_events': self.event_count(),
        }

    def report_text(self) -> str:
        s = self.summary()
        return (
            f'GraphQL Subscription Engine\n'
            f'  Active subscribers: {s["active_subscribers"]}\n'
            f'  Total events published: {s["total_events"]}'
        )

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        sp = os.path.join(dir, 'graphql_subscriptions.json')
        with open(sp, 'w') as f:
            json.dump(self.summary(), f, indent=2)
        paths.append(sp)
        return paths
