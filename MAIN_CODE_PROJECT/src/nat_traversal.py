"""NAT traversal and peer-to-peer connectivity using STUN, TURN, and ICE."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import datetime
import hashlib
import ipaddress
import json
import os
import random
import socket
import struct
import threading
import time
import uuid


_STUN_SERVERS = [
    ('stun.l.google.com', 19302),
    ('stun1.l.google.com', 19302),
]


class Candidate:
    """An ICE candidate — a potential connection endpoint."""

    def __init__(self, ip: str, port: int, proto: str = 'udp',
                 priority: int = 0, typ: str = 'host',
                 base_ip: str = '', base_port: int = 0) -> None:
        self.ip = ip
        self.port = port
        self.proto = proto
        self.priority = priority or self._default_priority(typ)
        self.typ = typ
        self.base_ip = base_ip or ip
        self.base_port = base_port or port
        self.id = uuid.uuid4().hex[:8]

    @staticmethod
    def _default_priority(typ: str) -> int:
        if typ == 'host':
            return 100
        if typ == 'srflx':
            return 80
        if typ == 'prflx':
            return 60
        if typ == 'relay':
            return 40
        return 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'ip': self.ip, 'port': self.port, 'proto': self.proto,
            'priority': self.priority, 'type': self.typ,
            'base_ip': self.base_ip, 'base_port': self.base_port,
            'id': self.id,
        }


class STUNClient:
    """STUN client for discovering public endpoints."""

    def __init__(self, server: Tuple[str, int] = _STUN_SERVERS[0], timeout: float = 3.0) -> None:
        self._server = server
        self._timeout = timeout

    def discover(self) -> Optional[Tuple[str, int]]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self._timeout)
            tid = random.randbytes(12)
            msg = struct.pack('!HHI', 0x0001, 0, len(tid)) + tid
            sock.sendto(msg, self._server)
            data, addr = sock.recvfrom(1024)
            sock.close()
            if len(data) < 20:
                return None
            offset = 20
            while offset < len(data):
                attr_type = struct.unpack('!H', data[offset:offset + 2])[0]
                attr_len = struct.unpack('!H', data[offset + 2:offset + 4])[0]
                if attr_type == 0x0020:
                    family = data[offset + 4]
                    port = struct.unpack('!H', data[offset + 6:offset + 8])[0]
                    if family == 0x01:
                        ip = socket.inet_ntoa(data[offset + 8:offset + 12])
                    else:
                        ip = socket.inet_ntop(socket.AF_INET6, data[offset + 8:offset + 24])
                    return (ip, port ^ 0x2112)
                offset += 4 + attr_len
            return None
        except Exception:
            return None

    @staticmethod
    def query_multiple(servers: List[Tuple[str, int]] = None,
                       timeout: float = 2.0) -> List[Tuple[str, int]]:
        servers = servers or _STUN_SERVERS
        results = []
        for srv in servers:
            client = STUNClient(srv, timeout)
            result = client.discover()
            if result:
                results.append(result)
        return results


class TURNRelay:
    """TURN relay server for relaying traffic when P2P is blocked."""

    def __init__(self, relay_host: str = '', relay_port: int = 3478,
                 username: str = '', password: str = '') -> None:
        self._host = relay_host
        self._port = relay_port
        self._username = username
        self._password = password
        self._allocated_ip: Optional[str] = None
        self._allocated_port: Optional[int] = None
        self._sock: Optional[socket.socket] = None

    def allocate(self, local_port: int = 0) -> bool:
        if not self._host:
            return False
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.settimeout(5.0)
            if local_port:
                self._sock.bind(('0.0.0.0', local_port))
            req = json.dumps({
                'method': 'allocate', 'username': self._username,
            }).encode()
            self._sock.sendto(req, (self._host, self._port))
            data, _ = self._sock.recvfrom(4096)
            resp = json.loads(data.decode())
            self._allocated_ip = resp.get('ip', self._host)
            self._allocated_port = resp.get('port', self._port)
            return True
        except Exception:
            return False

    def relay_endpoint(self) -> Optional[Tuple[str, int]]:
        if self._allocated_ip and self._allocated_port:
            return (self._allocated_ip, self._allocated_port)
        return None

    def close(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None


class ConnectivityChecker:
    """Checks connectivity between two endpoints."""

    @staticmethod
    def check(ip: str, port: int, timeout: float = 2.0) -> bool:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            sock.sendto(b'ping', (ip, port))
            data, _ = sock.recvfrom(1024)
            sock.close()
            return data == b'pong'
        except Exception:
            return False

    @staticmethod
    def listen(port: int, timeout: float = 5.0) -> List[Tuple[str, int]]:
        results = []
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        sock.bind(('0.0.0.0', port))
        end = time.time() + timeout
        while time.time() < end:
            try:
                data, addr = sock.recvfrom(1024)
                if data == b'ping':
                    sock.sendto(b'pong', addr)
                    results.append(addr)
            except socket.timeout:
                break
            except Exception:
                break
        sock.close()
        return results


class ICEEngine:
    """ICE (Interactive Connectivity Establishment) agent."""

    def __init__(self, local_ip: str = '0.0.0.0', local_port: int = 0) -> None:
        self._local_ip = local_ip
        self._local_port = local_port or self._random_port()
        self._candidates: List[Candidate] = []
        self._remote_candidates: List[Candidate] = []
        self._stun_client = STUNClient()
        self._turn: Optional[TURNRelay] = None
        self._selected: Optional[Tuple[str, int]] = None
        self._lock = threading.Lock()

    @staticmethod
    def _random_port() -> int:
        return random.randint(10000, 60000)

    def gather_candidates(self, use_stun: bool = True, use_turn: bool = False,
                          turn_config: Optional[Dict[str, Any]] = None) -> List[Candidate]:
        with self._lock:
            self._candidates.clear()
            self._candidates.append(Candidate(
                self._local_ip, self._local_port, typ='host',
            ))
            local_ips = self._local_ips()
            for ip in local_ips:
                self._candidates.append(Candidate(ip, self._local_port, typ='host'))

        if use_stun:
            endpoints = STUNClient.query_multiple()
            for ep in endpoints[:2]:
                with self._lock:
                    self._candidates.append(Candidate(ep[0], ep[1], typ='srflx'))

        if use_turn and turn_config:
            self._turn = TURNRelay(
                turn_config.get('host', ''),
                turn_config.get('port', 3478),
                turn_config.get('username', ''),
                turn_config.get('password', ''),
            )
            if self._turn.allocate(self._local_port):
                ep = self._turn.relay_endpoint()
                if ep:
                    with self._lock:
                        self._candidates.append(Candidate(ep[0], ep[1], typ='relay'))

        with self._lock:
            return list(self._candidates)

    def _local_ips(self) -> List[str]:
        ips = []
        try:
            hostname = socket.gethostname()
            for info in socket.getaddrinfo(hostname, None):
                ip = info[4][0]
                if not ip.startswith('127.'):
                    ips.append(ip)
        except Exception:
            pass
        return ips

    def set_remote_candidates(self, candidates: List[Candidate]) -> None:
        with self._lock:
            self._remote_candidates = list(candidates)

    def select_candidate_pair(self, timeout: float = 3.0) -> Optional[Tuple[str, int]]:
        with self._lock:
            local = list(self._candidates)
            remote = list(self._remote_candidates)

        pairs = []
        for lc in local:
            for rc in remote:
                pairs.append((lc, rc, lc.priority + rc.priority))

        pairs.sort(key=lambda x: -x[2])

        for lc, rc, _ in pairs:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            try:
                sock.bind((lc.ip, lc.port) if lc.typ == 'host' else (self._local_ip, self._local_port))
                sock.sendto(b'ice-ping', (rc.ip, rc.port))
                data, addr = sock.recvfrom(1024)
                if data == b'ice-pong':
                    self._selected = (rc.ip, rc.port)
                    sock.close()
                    return self._selected
            except Exception:
                pass
            finally:
                try:
                    sock.close()
                except Exception:
                    pass
        return None

    @property
    def selected(self) -> Optional[Tuple[str, int]]:
        return self._selected

    def candidates(self) -> List[Candidate]:
        with self._lock:
            return list(self._candidates)


class NATTraversalManager:
    """High-level NAT traversal with STUN/TURN/ICE orchestration."""

    def __init__(self, local_port: int = 0) -> None:
        self._engine = ICEEngine('0.0.0.0', local_port)
        self._peer_connections: Dict[str, Tuple[str, int]] = {}
        self._lock = threading.Lock()
        self._listener_sock: Optional[socket.socket] = None
        self._running = False

    def discover_public(self) -> Optional[Tuple[str, int]]:
        return self._engine._stun_client.discover()

    def gather(self, use_stun: bool = True, use_turn: bool = False,
               turn_config: Optional[Dict[str, Any]] = None) -> List[Candidate]:
        return self._engine.gather_candidates(use_stun, use_turn, turn_config)

    def connect_to_peer(self, peer_id: str, remote_candidates: List[Candidate],
                        timeout: float = 5.0) -> bool:
        self._engine.set_remote_candidates(remote_candidates)
        selected = self._engine.select_candidate_pair(timeout)
        if selected:
            with self._lock:
                self._peer_connections[peer_id] = selected
            return True
        return False

    def candidate_summary(self) -> Dict[str, Any]:
        return {
            'local_candidates': [c.to_dict() for c in self._engine.candidates()],
            'active_peers': list(self._peer_connections.keys()),
        }

    def start_listener(self, port: int = 0) -> int:
        self._listener_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._listener_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener_sock.bind(('0.0.0.0', port))
        actual_port = self._listener_sock.getsockname()[1]
        self._running = True
        t = threading.Thread(target=self._listen_loop, daemon=True)
        t.start()
        return actual_port

    def _listen_loop(self) -> None:
        while self._running:
            try:
                data, addr = self._listener_sock.recvfrom(1024)
            except Exception:
                break

    def stop_listener(self) -> None:
        self._running = False
        if self._listener_sock:
            try:
                self._listener_sock.close()
            except Exception:
                pass
            self._listener_sock = None

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        sp = os.path.join(dir, 'nat_traversal.json')
        with open(sp, 'w') as f:
            json.dump(self.candidate_summary(), f, indent=2, default=str)
        paths.append(sp)
        return paths
