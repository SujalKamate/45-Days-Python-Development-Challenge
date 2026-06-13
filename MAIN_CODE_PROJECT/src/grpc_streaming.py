"""Bidirectional gRPC-style streaming infrastructure for remote module execution."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple
import datetime
import json
import os
import queue
import socket
import ssl
import struct
import threading
import time
import uuid
import zlib


_PROTOCOL_VERSION = 1
_FRAME_HEADER_SIZE = 5


class Frame:
    """Wire format frame: type + payload."""

    FRAME_TYPES = {
        'EXEC': 1, 'LOG': 2, 'STATE': 3, 'PROGRESS': 4,
        'RESULT': 5, 'CANCEL': 6, 'ACK': 7, 'ERROR': 8,
        'HEARTBEAT': 9, 'COMPLETE': 10,
    }

    def __init__(self, frame_type: str, payload: bytes, stream_id: str = '') -> None:
        self.type = frame_type
        self.type_code = self.FRAME_TYPES.get(frame_type, 0)
        self.payload = payload
        self.stream_id = stream_id

    def encode(self) -> bytes:
        header = struct.pack('!BB', _PROTOCOL_VERSION, self.type_code)
        payload_compressed = zlib.compress(self.payload)
        body = json.dumps({'sid': self.stream_id}).encode() + b'\n' + payload_compressed
        length = struct.pack('!I', len(body))
        return header + length + body

    @staticmethod
    def decode(data: bytes) -> Frame:
        version = data[0]
        type_code = data[1]
        length = struct.unpack('!I', data[2:6])[0]
        body = data[6:6 + length]
        sid_end = body.index(b'\n')
        sid_data = json.loads(body[:sid_end].decode())
        payload = zlib.decompress(body[sid_end + 1:])
        rev_map = {v: k for k, v in Frame.FRAME_TYPES.items()}
        frame_type = rev_map.get(type_code, 'UNKNOWN')
        return Frame(frame_type, payload, sid_data.get('sid', ''))


class Stream:
    """Bidirectional stream identified by a unique ID."""

    def __init__(self, stream_id: str) -> None:
        self.id = stream_id
        self._send_queue: queue.Queue = queue.Queue()
        self._recv_queue: queue.Queue = queue.Queue()
        self._cancel_event = threading.Event()
        self._complete_event = threading.Event()
        self._error: Optional[str] = None
        self._lock = threading.Lock()

    def send(self, frame_type: str, data: Any) -> None:
        payload = json.dumps(data, default=str).encode('utf-8')
        self._send_queue.put(Frame(frame_type, payload, self.id))

    def recv(self, timeout: float = 1.0) -> Optional[Frame]:
        try:
            return self._recv_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def push_frame(self, frame: Frame) -> None:
        self._recv_queue.put(frame)

    def cancel(self) -> None:
        self._cancel_event.set()
        self.send('CANCEL', {'reason': 'user cancelled'})

    @property
    def cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def mark_complete(self) -> None:
        self._complete_event.set()

    @property
    def complete(self) -> bool:
        return self._complete_event.is_set()

    @property
    def error(self) -> Optional[str]:
        with self._lock:
            return self._error

    @error.setter
    def error(self, val: str) -> None:
        with self._lock:
            self._error = val


class StreamManager:
    """Manages active streams."""

    def __init__(self) -> None:
        self._streams: Dict[str, Stream] = {}
        self._lock = threading.Lock()

    def create(self) -> Stream:
        sid = uuid.uuid4().hex[:16]
        stream = Stream(sid)
        with self._lock:
            self._streams[sid] = stream
        return stream

    def get(self, sid: str) -> Optional[Stream]:
        with self._lock:
            return self._streams.get(sid)

    def remove(self, sid: str) -> None:
        with self._lock:
            self._streams.pop(sid, None)

    def active_count(self) -> int:
        with self._lock:
            return len(self._streams)

    def cancel_all(self) -> None:
        with self._lock:
            for s in self._streams.values():
                s.cancel()


class TLSConfig:
    """TLS configuration for secure gRPC-style communication."""

    def __init__(self, cert_path: str = '', key_path: str = '', ca_path: str = '', insecure: bool = False) -> None:
        self.cert_path = cert_path
        self.key_path = key_path
        self.ca_path = ca_path
        self.insecure = insecure

    def server_context(self) -> ssl.SSLContext:
        ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        if not self.insecure:
            ctx.load_cert_chain(self.cert_path, self.key_path)
            if self.ca_path:
                ctx.load_verify_locations(self.ca_path)
                ctx.verify_mode = ssl.CERT_REQUIRED
        else:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        return ctx

    def client_context(self) -> ssl.SSLContext:
        ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        if self.insecure:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        else:
            if self.ca_path:
                ctx.load_verify_locations(self.ca_path)
            if self.cert_path and self.key_path:
                ctx.load_cert_chain(self.cert_path, self.key_path)
        return ctx


class GRPCServer:
    """gRPC-style server handling bidirectional streams."""

    def __init__(self, host: str = '0.0.0.0', port: int = 50051, tls: Optional[TLSConfig] = None) -> None:
        self._host = host
        self._port = port
        self._tls = tls or TLSConfig(insecure=True)
        self._manager = StreamManager()
        self._handlers: Dict[str, Callable] = {}
        self._running = False
        self._server_socket: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None

    def register_handler(self, name: str, handler: Callable[[Stream, Dict[str, Any]], None]) -> None:
        self._handlers[name] = handler

    def start(self) -> None:
        self._running = True
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self._host, self._port))
        self._server_socket.listen(10)
        self._server_socket.settimeout(1.0)
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        self._manager.cancel_all()

    def _accept_loop(self) -> None:
        ctx = self._tls.server_context()
        while self._running:
            try:
                conn, addr = self._server_socket.accept()
                tls_conn = ctx.wrap_socket(conn, server_side=True)
                client_thread = threading.Thread(
                    target=self._handle_client, args=(tls_conn, addr), daemon=True
                )
                client_thread.start()
            except socket.timeout:
                continue
            except Exception:
                continue

    def _handle_client(self, conn: ssl.SSLSocket, addr: Any) -> None:
        stream = self._manager.create()
        buffer = b''
        try:
            while self._running and not stream.cancelled:
                try:
                    data = conn.recv(4096)
                except Exception:
                    break
                if not data:
                    break
                buffer += data
                while len(buffer) >= 6:
                    body_len = struct.unpack('!I', buffer[2:6])[0]
                    frame_size = 6 + body_len
                    if len(buffer) < frame_size:
                        break
                    frame_data = buffer[:frame_size]
                    buffer = buffer[frame_size:]
                    frame = Frame.decode(frame_data)
                    if frame.type == 'EXEC':
                        req = json.loads(frame.payload.decode())
                        handler = self._handlers.get(req.get('method', ''))
                        if handler:
                            t = threading.Thread(
                                target=self._run_handler,
                                args=(handler, stream, req.get('params', {})),
                                daemon=True,
                            )
                            t.start()
                        else:
                            stream.send('ERROR', {'message': f'unknown method: {req.get("method")}'})
                    elif frame.type == 'CANCEL':
                        stream.cancel()
                    elif frame.type == 'HEARTBEAT':
                        stream.send('ACK', {'heartbeat': True})
        finally:
            self._manager.remove(stream.id)
            try:
                conn.close()
            except Exception:
                pass

    def _run_handler(self, handler: Callable, stream: Stream, params: Dict[str, Any]) -> None:
        try:
            handler(stream, params)
        except Exception as e:
            stream.send('ERROR', {'message': str(e)})
        finally:
            stream.send('COMPLETE', {})
            stream.mark_complete()

    @property
    def address(self) -> str:
        return f'{self._host}:{self._port}'


class GRPCClient:
    """gRPC-style client for remote execution with streaming."""

    def __init__(self, host: str = 'localhost', port: int = 50051, tls: Optional[TLSConfig] = None) -> None:
        self._host = host
        self._port = port
        self._tls = tls or TLSConfig(insecure=True)
        self._conn: Optional[ssl.SSLSocket] = None
        self._lock = threading.Lock()

    def connect(self) -> None:
        ctx = self._tls.client_context()
        raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._conn = ctx.wrap_socket(raw, server_hostname=self._host)
        self._conn.connect((self._host, self._port))

    def disconnect(self) -> None:
        with self._lock:
            if self._conn:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None

    def execute(self, method: str, params: Dict[str, Any] = None) -> Stream:
        stream = Stream(uuid.uuid4().hex[:16])
        req = {'method': method, 'params': params or {}}
        stream.send('EXEC', req)
        self._send_frame(stream)
        t = threading.Thread(target=self._recv_loop, args=(stream,), daemon=True)
        t.start()
        return stream

    def _send_frame(self, stream: Stream) -> None:
        while True:
            try:
                frame = stream._send_queue.get(timeout=0.1)
            except queue.Empty:
                if stream.complete or stream.cancelled:
                    break
                continue
            data = frame.encode()
            with self._lock:
                if self._conn:
                    try:
                        self._conn.sendall(data)
                    except Exception:
                        break
            if frame.type in ('CANCEL', 'COMPLETE'):
                break

    def _recv_loop(self, stream: Stream) -> None:
        buffer = b''
        while not stream.complete and not stream.cancelled:
            with self._lock:
                if not self._conn:
                    break
                try:
                    data = self._conn.recv(4096)
                except Exception:
                    break
            if not data:
                break
            buffer += data
            while len(buffer) >= 6:
                body_len = struct.unpack('!I', buffer[2:6])[0]
                frame_size = 6 + body_len
                if len(buffer) < frame_size:
                    break
                frame_data = buffer[:frame_size]
                buffer = buffer[frame_size:]
                frame = Frame.decode(frame_data)
                stream.push_frame(frame)
                if frame.type == 'COMPLETE':
                    stream.mark_complete()
                elif frame.type == 'ERROR':
                    stream.error = frame.payload.decode()

    def recv_events(self, stream: Stream, timeout: float = 0.5) -> List[Dict[str, Any]]:
        events = []
        while True:
            frame = stream.recv(timeout)
            if frame is None:
                break
            events.append({
                'type': frame.type,
                'data': json.loads(frame.payload.decode()),
                'stream_id': frame.stream_id,
            })
        return events

    @property
    def connected(self) -> bool:
        return self._conn is not None


class RemoteExecutor:
    """High-level remote execution interface with progress, log, and state streaming."""

    def __init__(self, host: str = 'localhost', port: int = 50051, tls: Optional[TLSConfig] = None) -> None:
        self._client = GRPCClient(host, port, tls)

    def connect(self) -> None:
        self._client.connect()

    def disconnect(self) -> None:
        self._client.disconnect()

    def run(self, method: str, params: Dict[str, Any] = None, timeout_s: float = 30.0) -> Dict[str, Any]:
        stream = self._client.execute(method, params)
        logs: List[str] = []
        states: List[Dict[str, Any]] = []
        result: Any = None
        error: Optional[str] = None
        start = time.time()

        while not stream.complete and not stream.cancelled and (time.time() - start) < timeout_s:
            events = self._client.recv_events(stream)
            for ev in events:
                if ev['type'] == 'LOG':
                    logs.append(str(ev['data'].get('message', '')))
                elif ev['type'] == 'STATE':
                    states.append(ev['data'])
                elif ev['type'] == 'PROGRESS':
                    pass
                elif ev['type'] == 'RESULT':
                    result = ev['data']
                elif ev['type'] == 'ERROR':
                    error = ev['data'].get('message', str(ev['data']))
                elif ev['type'] == 'COMPLETE':
                    stream.mark_complete()

        return {
            'result': result,
            'logs': logs,
            'states': states,
            'error': error,
            'complete': stream.complete,
        }

    def run_async(self, method: str, params: Dict[str, Any] = None) -> Stream:
        return self._client.execute(method, params)

    @property
    def connected(self) -> bool:
        return self._client.connected
