"""Persistent reliable messaging with at-least-once delivery guarantees."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import datetime
import hashlib
import json
import os
import queue
import threading
import time
import uuid


_REDELIVERY_DELAY_S = 5.0
_MAX_REDELIVERIES = 10
_ACK_TIMEOUT_S = 30.0
_SEGMENT_SIZE = 1000


def _msg_id() -> str:
    return uuid.uuid4().hex[:16]


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class Message:
    """A persistent message with delivery tracking."""

    def __init__(self, topic: str, payload: Any, key: str = '',
                 msg_id: str = '', headers: Optional[Dict[str, str]] = None) -> None:
        self.id = msg_id or _msg_id()
        self.topic = topic
        self.payload = payload
        self.key = key or self.id
        self.headers = headers or {}
        self.created_at = _now_iso()
        self.deliveries: int = 0
        self.last_delivery: Optional[str] = None
        self.acked: bool = False
        self._offset: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'topic': self.topic,
            'payload': self.payload,
            'key': self.key,
            'headers': self.headers,
            'created_at': self.created_at,
            'deliveries': self.deliveries,
            'last_delivery': self.last_delivery,
            'acked': self.acked,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> Message:
        m = Message(d['topic'], d['payload'], d.get('key', ''), d['id'], d.get('headers', {}))
        m.created_at = d.get('created_at', m.created_at)
        m.deliveries = d.get('deliveries', 0)
        m.last_delivery = d.get('last_delivery')
        m.acked = d.get('acked', False)
        return m


class MessageStore:
    """Persistent message store using append-ahead-log segments."""

    def __init__(self, base_dir: str = '.msg_store') -> None:
        self._base = base_dir
        self._segments: Dict[str, int] = {}
        self._lock = threading.Lock()
        os.makedirs(self._base, exist_ok=True)

    def append(self, topic: str, message: Message) -> int:
        with self._lock:
            seg = self._segments.get(topic, 0)
            seg_path = os.path.join(self._base, f'{topic}_{seg}.log')
            if not os.path.exists(seg_path) or os.path.getsize(seg_path) > 1024 * 1024:
                seg += 1
                self._segments[topic] = seg
                seg_path = os.path.join(self._base, f'{topic}_{seg}.log')
            with open(seg_path, 'a') as f:
                line = json.dumps(message.to_dict(), default=str) + '\n'
                f.write(line)
            return seg

    def read_all(self, topic: str) -> List[Message]:
        messages = []
        seg = 0
        while True:
            seg_path = os.path.join(self._base, f'{topic}_{seg}.log')
            if not os.path.exists(seg_path):
                break
            with open(seg_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        messages.append(Message.from_dict(json.loads(line)))
            seg += 1
        return messages

    def read_from(self, topic: str, offset: int) -> List[Message]:
        return self.read_all(topic)[offset:]

    def delete_topic(self, topic: str) -> None:
        seg = 0
        while True:
            seg_path = os.path.join(self._base, f'{topic}_{seg}.log')
            if not os.path.exists(seg_path):
                break
            os.remove(seg_path)
            seg += 1


class AckTracker:
    """Tracks message acknowledgments with timeout/redelivery."""

    def __init__(self) -> None:
        self._pending: Dict[str, Tuple[Message, float]] = {}
        self._lock = threading.Lock()

    def track(self, msg: Message, timeout_s: float = _ACK_TIMEOUT_S) -> None:
        with self._lock:
            self._pending[msg.id] = (msg, time.time() + timeout_s)

    def ack(self, msg_id: str) -> bool:
        with self._lock:
            return self._pending.pop(msg_id, None) is not None

    def unacked(self) -> List[Message]:
        with self._lock:
            now = time.time()
            expired = [(m, deadline) for m, deadline in self._pending.values() if deadline <= now]
            for m, _ in expired:
                m.deliveries += 1
                m.last_delivery = _now_iso()
            return [m for m, _ in expired]

    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)

    def clear(self) -> None:
        with self._lock:
            self._pending.clear()


class Partition:
    """A message partition within a topic."""

    def __init__(self, topic: str, partition_id: int) -> None:
        self.topic = topic
        self.id = partition_id
        self._messages: List[Message] = []
        self._offset: int = 0
        self._lock = threading.Lock()

    def append(self, msg: Message) -> None:
        with self._lock:
            self._messages.append(msg)

    def read(self, batch_size: int = 10) -> List[Message]:
        with self._lock:
            end = min(self._offset + batch_size, len(self._messages))
            batch = self._messages[self._offset:end]
            self._offset = end
            return batch

    @property
    def offset(self) -> int:
        with self._lock:
            return self._offset

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._messages)

    def reset_offset(self, offset: int = 0) -> None:
        with self._lock:
            self._offset = offset


class ConsumerGroup:
    """Consumer group with partition assignment and offset tracking."""

    def __init__(self, group_id: str) -> None:
        self.id = group_id
        self._offsets: Dict[str, int] = {}
        self._members: Set[str] = set()
        self._lock = threading.Lock()

    def join(self, consumer_id: str) -> None:
        with self._lock:
            self._members.add(consumer_id)

    def leave(self, consumer_id: str) -> None:
        with self._lock:
            self._members.discard(consumer_id)

    def commit_offset(self, topic: str, offset: int) -> None:
        with self._lock:
            self._offsets[topic] = max(self._offsets.get(topic, 0), offset)

    def last_offset(self, topic: str) -> int:
        with self._lock:
            return self._offsets.get(topic, 0)

    @property
    def member_count(self) -> int:
        with self._lock:
            return len(self._members)


class ReliableMessagingBroker:
    """Message broker with persistence, acks, redelivery, and consumer groups."""

    def __init__(self, store_dir: str = '.msg_store') -> None:
        self._store = MessageStore(store_dir)
        self._ack_tracker = AckTracker()
        self._partitions: Dict[str, List[Partition]] = {}
        self._consumer_groups: Dict[str, ConsumerGroup] = {}
        self._subscriptions: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()
        self._running = False
        self._redeliver_thread: Optional[threading.Thread] = None

    def create_topic(self, topic: str, partitions: int = 1) -> None:
        with self._lock:
            if topic not in self._partitions:
                self._partitions[topic] = [Partition(topic, i) for i in range(partitions)]
                self._subscriptions[topic] = []

    def publish(self, topic: str, payload: Any, key: str = '',
                headers: Optional[Dict[str, str]] = None) -> Message:
        msg = Message(topic, payload, key, headers=headers)
        self._store.append(topic, msg)
        partition = self._get_partition(topic, key)
        partition.append(msg)
        self._ack_tracker.track(msg)
        self._dispatch(topic, msg)
        return msg

    def _get_partition(self, topic: str, key: str) -> Partition:
        with self._lock:
            parts = self._partitions.get(topic, [])
            if not parts:
                parts = [Partition(topic, 0)]
                self._partitions[topic] = parts
            idx = abs(hash(key)) % len(parts) if key else 0
            return parts[idx]

    def subscribe(self, topic: str, callback: Callable[[Message], None]) -> None:
        with self._lock:
            if topic not in self._subscriptions:
                self._subscriptions[topic] = []
            self._subscriptions[topic].append(callback)

    def _dispatch(self, topic: str, msg: Message) -> None:
        with self._lock:
            callbacks = list(self._subscriptions.get(topic, []))
        for cb in callbacks:
            try:
                cb(msg)
            except Exception:
                pass

    def ack(self, msg_id: str) -> bool:
        return self._ack_tracker.ack(msg_id)

    def start_redelivery_engine(self, interval_s: float = _REDELIVERY_DELAY_S) -> None:
        if self._running:
            return
        self._running = True
        self._redeliver_thread = threading.Thread(
            target=self._redelivery_loop, args=(interval_s,), daemon=True
        )
        self._redeliver_thread.start()

    def stop_redelivery_engine(self) -> None:
        self._running = False

    def _redelivery_loop(self, interval_s: float) -> None:
        while self._running:
            unacked = self._ack_tracker.unacked()
            for msg in unacked:
                if msg.deliveries >= _MAX_REDELIVERIES:
                    continue
                self._dispatch(msg.topic, msg)
                self._ack_tracker.track(msg, _ACK_TIMEOUT_S)
            time.sleep(interval_s)

    def create_consumer_group(self, group_id: str) -> ConsumerGroup:
        with self._lock:
            if group_id not in self._consumer_groups:
                self._consumer_groups[group_id] = ConsumerGroup(group_id)
            return self._consumer_groups[group_id]

    def consume(self, topic: str, group: ConsumerGroup, batch_size: int = 10) -> List[Message]:
        offset = group.last_offset(topic)
        messages = self._store.read_from(topic, offset)
        batch = messages[:batch_size]
        if batch:
            group.commit_offset(topic, offset + len(batch))
        return batch

    def consume_and_ack(self, topic: str, group: ConsumerGroup, batch_size: int = 10) -> List[Message]:
        messages = self.consume(topic, group, batch_size)
        for m in messages:
            self.ack(m.id)
        return messages

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'topics': list(self._partitions.keys()),
                'pending_acks': self._ack_tracker.pending_count(),
                'consumer_groups': list(self._consumer_groups.keys()),
                'partitions': {t: len(ps) for t, ps in self._partitions.items()},
            }

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        sp = os.path.join(dir, 'messaging_summary.json')
        with open(sp, 'w') as f:
            json.dump(self.summary(), f, indent=2)
        paths.append(sp)
        return paths


class PersistentMessagingClient:
    """Client interface for the reliable messaging system."""

    def __init__(self, broker: ReliableMessagingBroker, client_id: str = '') -> None:
        self._broker = broker
        self.id = client_id or f'client-{uuid.uuid4().hex[:8]}'
        self._group: Optional[ConsumerGroup] = None

    def join_group(self, group_id: str) -> ConsumerGroup:
        self._group = self._broker.create_consumer_group(group_id)
        self._group.join(self.id)
        return self._group

    def leave_group(self) -> None:
        if self._group:
            self._group.leave(self.id)
            self._group = None

    def publish(self, topic: str, payload: Any, key: str = '',
                headers: Optional[Dict[str, str]] = None) -> Message:
        return self._broker.publish(topic, payload, key, headers)

    def subscribe(self, topic: str, callback: Callable[[Message], None]) -> None:
        self._broker.subscribe(topic, callback)

    def consume(self, topic: str, batch_size: int = 10) -> List[Message]:
        if self._group is None:
            return []
        return self._broker.consume(topic, self._group, batch_size)

    def consume_and_ack(self, topic: str, batch_size: int = 10) -> List[Message]:
        if self._group is None:
            return []
        return self._broker.consume_and_ack(topic, self._group, batch_size)

    def ack(self, msg_id: str) -> bool:
        return self._broker.ack(msg_id)
