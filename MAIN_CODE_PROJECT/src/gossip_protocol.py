"""UDP-based gossip protocol for automatic node discovery and cluster membership."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import datetime
import json
import os
import random
import socket
import struct
import threading
import time
import uuid


_GOSSIP_INTERVAL = 2.0
_FAILURE_TIMEOUT = 10.0
_CLEANUP_INTERVAL = 15.0
_GOSSIP_FANOUT = 3
_MAX_PEERS = 50


def _node_id() -> str:
    return uuid.uuid4().hex[:12]


def _now_epoch() -> float:
    return time.time()


class NodeState:
    """State of a single cluster node."""

    ALIVE = 'alive'
    SUSPECT = 'suspect'
    DEAD = 'dead'

    def __init__(self, node_id: str, host: str, port: int, incarnation: int = 0) -> None:
        self.node_id = node_id
        self.host = host
        self.port = port
        self.status = self.ALIVE
        self.incarnation = incarnation
        self.last_seen = _now_epoch()
        self.last_updated = _now_epoch()

    def mark_alive(self, incarnation: Optional[int] = None) -> None:
        self.status = self.ALIVE
        if incarnation is not None:
            self.incarnation = max(self.incarnation, incarnation)
        self.last_seen = _now_epoch()
        self.last_updated = _now_epoch()

    def mark_suspect(self) -> None:
        if self.status == self.ALIVE:
            self.status = self.SUSPECT
            self.last_updated = _now_epoch()

    def mark_dead(self) -> None:
        if self.status != self.DEAD:
            self.status = self.DEAD
            self.last_updated = _now_epoch()

    @property
    def is_expired(self, timeout: float = _FAILURE_TIMEOUT) -> bool:
        return (_now_epoch() - self.last_seen) > timeout

    def to_dict(self) -> Dict[str, Any]:
        return {
            'node_id': self.node_id,
            'host': self.host,
            'port': self.port,
            'status': self.status,
            'incarnation': self.incarnation,
            'last_seen': self.last_seen,
            'last_updated': self.last_updated,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> NodeState:
        ns = NodeState(d['node_id'], d['host'], d['port'], d.get('incarnation', 0))
        ns.status = d.get('status', 'alive')
        ns.last_seen = d.get('last_seen', 0)
        ns.last_updated = d.get('last_updated', 0)
        return ns


class MembershipList:
    """Thread-safe membership list with failure detection."""

    def __init__(self, local: NodeState) -> None:
        self._local = local
        self._nodes: Dict[str, NodeState] = {local.node_id: local}
        self._lock = threading.Lock()
        self._handlers: List[Callable] = []

    @property
    def local(self) -> NodeState:
        return self._local

    def add_or_update(self, state: NodeState) -> bool:
        changed = False
        with self._lock:
            existing = self._nodes.get(state.node_id)
            if existing is None:
                self._nodes[state.node_id] = state
                changed = True
            elif state.incarnation > existing.incarnation or (
                state.incarnation == existing.incarnation and state.status != existing.status
            ):
                if state.status == 'alive' and existing.status in ('suspect', 'dead'):
                    state.incarnation = max(state.incarnation, existing.incarnation + 1)
                self._nodes[state.node_id] = state
                changed = True
        if changed:
            self._notify(state)
        return changed

    def suspect(self, node_id: str) -> None:
        with self._lock:
            node = self._nodes.get(node_id)
            if node and node.node_id != self._local.node_id:
                node.mark_suspect()
                self._notify(node)

    def mark_dead(self, node_id: str) -> None:
        with self._lock:
            node = self._nodes.get(node_id)
            if node and node.node_id != self._local.node_id:
                node.mark_dead()
                self._notify(node)

    def alive_nodes(self, exclude_self: bool = True) -> List[NodeState]:
        with self._lock:
            return [
                n for n in self._nodes.values()
                if n.status == 'alive' and (not exclude_self or n.node_id != self._local.node_id)
            ]

    def all_nodes(self) -> List[NodeState]:
        with self._lock:
            return list(self._nodes.values())

    def get(self, node_id: str) -> Optional[NodeState]:
        with self._lock:
            return self._nodes.get(node_id)

    def check_failures(self, timeout: float = _FAILURE_TIMEOUT) -> List[str]:
        failed = []
        with self._lock:
            for n in self._nodes.values():
                if n.node_id != self._local.node_id and n.is_expired(timeout) and n.status != 'dead':
                    if n.status == 'suspect':
                        n.mark_dead()
                        failed.append(n.node_id)
                    else:
                        n.mark_suspect()
        for fid in failed:
            self._notify(self._nodes.get(fid))
        return failed

    def cleanup_dead(self, max_age: float = 60.0) -> int:
        count = 0
        now = _now_epoch()
        with self._lock:
            dead_ids = [
                nid for nid, n in self._nodes.items()
                if n.status == 'dead' and (now - n.last_updated) > max_age
            ]
            for did in dead_ids:
                del self._nodes[did]
                count += 1
        return count

    def subscribe(self, handler: Callable[[NodeState], None]) -> None:
        self._handlers.append(handler)

    def _notify(self, state: Optional[NodeState]) -> None:
        if state is None:
            return
        for h in self._handlers:
            try:
                h(state)
            except Exception:
                pass

    def gossip_payload(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [n.to_dict() for n in self._nodes.values()]

    @staticmethod
    def from_payload(local: NodeState, payload: List[Dict[str, Any]]) -> MembershipList:
        ml = MembershipList(local)
        for d in payload:
            ml.add_or_update(NodeState.from_dict(d))
        return ml


class UDPGossipTransport:
    """UDP transport for gossip messages."""

    def __init__(self, host: str = '0.0.0.0', port: int = 0, broadcast: bool = True) -> None:
        self._host = host
        self._port = port
        self._broadcast = broadcast
        self._socket: Optional[socket.socket] = None
        self._running = False

    def start(self) -> None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.settimeout(0.5)
        if self._broadcast:
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._socket.bind((self._host, self._port))
        self._running = True

    def stop(self) -> None:
        self._running = False
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

    def send(self, data: bytes, target: Tuple[str, int]) -> None:
        if self._socket:
            try:
                self._socket.sendto(data, target)
            except Exception:
                pass

    def send_broadcast(self, data: bytes, port: int) -> None:
        if self._socket and self._broadcast:
            try:
                self._socket.sendto(data, ('<broadcast>', port))
            except Exception:
                pass

    def recv(self) -> Optional[Tuple[bytes, Tuple[str, int]]]:
        if not self._socket:
            return None
        try:
            data, addr = self._socket.recvfrom(65535)
            return data, addr
        except socket.timeout:
            return None
        except Exception:
            return None


class GossipMessage:
    """Gossip protocol message envelope."""

    MSG_TYPES = {'SYNC': 1, 'ACK': 2, 'PING': 3, 'PONG': 4, 'JOIN': 5}

    def __init__(self, msg_type: str, sender_id: str, payload: Any) -> None:
        self.type = msg_type
        self.sender_id = sender_id
        self.payload = payload
        self.timestamp = _now_epoch()

    def encode(self) -> bytes:
        data = json.dumps({
            'type': self.MSG_TYPES.get(self.type, 0),
            'sender_id': self.sender_id,
            'payload': self.payload,
            'timestamp': self.timestamp,
        }, default=str).encode('utf-8')
        return struct.pack('!I', len(data)) + data

    @staticmethod
    def decode(raw: bytes) -> Optional[GossipMessage]:
        try:
            length = struct.unpack('!I', raw[:4])[0]
            data = json.loads(raw[4:4 + length].decode('utf-8'))
            rev = {v: k for k, v in GossipMessage.MSG_TYPES.items()}
            return GossipMessage(
                rev.get(data['type'], 'UNKNOWN'),
                data['sender_id'],
                data['payload'],
            )
        except Exception:
            return None


class GossipNode:
    """A single node participating in the gossip protocol."""

    def __init__(self, host: str = '0.0.0.0', port: int = 0,
                 seed_hosts: Optional[List[Tuple[str, int]]] = None) -> None:
        self._id = _node_id()
        self._host = host
        self._port = port
        self._transport = UDPGossipTransport(host, port, broadcast=True)
        self._state = NodeState(self._id, host, port)
        self._membership = MembershipList(self._state)
        self._seed_hosts = seed_hosts or []
        self._running = False
        self._gossip_thread: Optional[threading.Thread] = None
        self._failure_thread: Optional[threading.Thread] = None
        self._listener_thread: Optional[threading.Thread] = None
        self._data_store: Dict[str, Any] = {}

    @property
    def node_id(self) -> str:
        return self._id

    @property
    def membership(self) -> MembershipList:
        return self._membership

    def set_data(self, key: str, value: Any) -> None:
        self._data_store[key] = value

    def get_data(self, key: str) -> Optional[Any]:
        return self._data_store.get(key)

    def start(self) -> None:
        self._transport.start()
        self._port = self._transport._socket.getsockname()[1] if self._transport._socket else self._port
        self._state.port = self._port
        self._running = True
        self._listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listener_thread.start()
        self._gossip_thread = threading.Thread(target=self._gossip_loop, daemon=True)
        self._gossip_thread.start()
        self._failure_thread = threading.Thread(target=self._failure_loop, daemon=True)
        self._failure_thread.start()
        for seed in self._seed_hosts:
            self._send_join(seed)

    def stop(self) -> None:
        self._running = False
        self._transport.stop()

    def _listen_loop(self) -> None:
        while self._running:
            result = self._transport.recv()
            if result is None:
                continue
            data, addr = result
            msg = GossipMessage.decode(data)
            if msg is None:
                continue
            if msg.type == 'SYNC':
                self._handle_sync(msg, addr)
            elif msg.type == 'PING':
                self._handle_ping(msg, addr)
            elif msg.type == 'JOIN':
                self._handle_join(msg, addr)
            elif msg.type == 'PONG':
                self._handle_pong(msg, addr)
            elif msg.type == 'ACK':
                pass

    def _handle_sync(self, msg: GossipMessage, addr: Tuple[str, int]) -> None:
        remote_nodes = msg.payload.get('nodes', [])
        remote_data = msg.payload.get('data', {})
        changed = False
        for nd in remote_nodes:
            ns = NodeState.from_dict(nd)
            if ns.node_id != self._id:
                if self._membership.add_or_update(ns):
                    changed = True
        for k, v in remote_data.items():
            if k not in self._data_store:
                self._data_store[k] = v
        ack = GossipMessage('ACK', self._id, {'node_id': self._id})
        self._transport.send(ack.encode(), addr)

    def _handle_ping(self, msg: GossipMessage, addr: Tuple[str, int]) -> None:
        pong = GossipMessage('PONG', self._id, {'node_id': self._id})
        self._transport.send(pong.encode(), addr)

    def _handle_join(self, msg: GossipMessage, addr: Tuple[str, int]) -> None:
        remote_id = msg.payload.get('node_id', '')
        remote = self._membership.get(remote_id)
        if remote is None:
            ns = NodeState(remote_id, addr[0], msg.payload.get('port', addr[1]))
            self._membership.add_or_update(ns)

    def _handle_pong(self, msg: GossipMessage, addr: Tuple[str, int]) -> None:
        remote_id = msg.payload.get('node_id', '')
        node = self._membership.get(remote_id)
        if node:
            node.mark_alive()

    def _send_join(self, target: Tuple[str, int]) -> None:
        msg = GossipMessage('JOIN', self._id, {
            'node_id': self._id, 'port': self._port, 'host': self._host,
        })
        self._transport.send(msg.encode(), target)

    def _gossip_loop(self) -> None:
        while self._running:
            time.sleep(_GOSSIP_INTERVAL)
            peers = self._membership.alive_nodes()
            if not peers:
                continue
            targets = random.sample(peers, min(_GOSSIP_FANOUT, len(peers)))
            payload = {
                'nodes': self._membership.gossip_payload(),
                'data': dict(self._data_store),
            }
            msg = GossipMessage('SYNC', self._id, payload)
            for t in targets:
                self._transport.send(msg.encode(), (t.host, t.port))

    def _failure_loop(self) -> None:
        while self._running:
            time.sleep(_CLEANUP_INTERVAL)
            self._membership.check_failures()
            self._membership.cleanup_dead()

    def summary(self) -> Dict[str, Any]:
        alive = self._membership.alive_nodes()
        all_nodes = self._membership.all_nodes()
        return {
            'node_id': self._id,
            'host': self._host,
            'port': self._port,
            'alive_peers': len(alive),
            'total_known': len(all_nodes),
            'peers': [{'id': n.node_id, 'host': n.host, 'port': n.port, 'status': n.status}
                      for n in all_nodes if n.node_id != self._id],
            'data_keys': list(self._data_store.keys()),
        }

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        sp = os.path.join(dir, 'gossip_state.json')
        with open(sp, 'w') as f:
            json.dump(self.summary(), f, indent=2, default=str)
        paths.append(sp)
        return paths
