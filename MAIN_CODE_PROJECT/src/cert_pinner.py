"""Certificate-pinned TLS validation for secure outbound communication."""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Set, Tuple
import datetime
import hashlib
import json
import logging
import os
import ssl
import threading
import urllib.request


logger = logging.getLogger(__name__)


def fingerprint_from_pem(pem_bytes: bytes) -> str:
    _, rest = pem_bytes.split(b'-----BEGIN CERTIFICATE-----\n', 1)
    der_data, _ = rest.split(b'\n-----END CERTIFICATE-----', 1)
    import base64
    der = base64.b64decode(der_data)
    return hashlib.sha256(der).hexdigest()


class PinSet:
    """Manages a set of pinned certificate fingerprints for a host."""

    def __init__(self, host: str, fingerprints: List[str]) -> None:
        self.host = host
        self._pins: Set[str] = set(fingerprints)
        self._backup: Set[str] = set()

    def match(self, fingerprint: str) -> bool:
        return fingerprint in self._pins or fingerprint in self._backup

    def add_pin(self, fingerprint: str) -> None:
        self._pins.add(fingerprint)

    def remove_pin(self, fingerprint: str) -> None:
        self._pins.discard(fingerprint)

    def rotate(self, new_fingerprints: List[str], keep_old: bool = True) -> None:
        if keep_old:
            self._backup = set(self._pins)
        else:
            self._backup.clear()
        self._pins = set(new_fingerprints)

    def all_pins(self) -> Set[str]:
        return self._pins | self._backup


class AuditLog:
    """Records TLS validation failures for security auditing."""

    def __init__(self, max_entries: int = 1000) -> None:
        self._entries: List[Dict[str, str]] = []
        self._max = max_entries
        self._lock = threading.Lock()

    def record(self, host: str, reason: str, fingerprint: Optional[str] = None) -> None:
        entry = {
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'host': host,
            'reason': reason,
        }
        if fingerprint:
            entry['fingerprint'] = fingerprint
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max:
                self._entries.pop(0)

    def recent(self, n: int = 10) -> List[Dict[str, str]]:
        with self._lock:
            return list(self._entries[-n:])

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


class CertificatePinner:
    """Validates TLS connections against pinned certificate fingerprints."""

    def __init__(self) -> None:
        self._pins: Dict[str, PinSet] = {}
        self._audit = AuditLog()
        self._lock = threading.Lock()

    def pin_host(self, host: str, fingerprints: List[str]) -> None:
        with self._lock:
            self._pins[host] = PinSet(host, fingerprints)

    def unpin_host(self, host: str) -> None:
        with self._lock:
            self._pins.pop(host, None)

    def rotate_host(self, host: str, new_fingerprints: List[str], keep_old: bool = True) -> None:
        with self._lock:
            ps = self._pins.get(host)
            if ps is None:
                self._pins[host] = PinSet(host, new_fingerprints)
            else:
                ps.rotate(new_fingerprints, keep_old)

    def host_pins(self, host: str) -> Set[str]:
        ps = self._pins.get(host)
        return set() if ps is None else ps.all_pins()

    def validate(self, host: str, port: int = 443) -> bool:
        context = ssl.create_default_context()
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED

        try:
            with socket_create_connection((host, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=host) as tls:
                    der = tls.getpeercert(binary_form=True)
                    if der is None:
                        self._audit.record(host, 'no peer certificate returned')
                        logger.warning('Certificate pinning failed for %s: no cert', host)
                        return False
                    fingerprint = hashlib.sha256(der).hexdigest()
                    with self._lock:
                        ps = self._pins.get(host)
                    if ps is None:
                        return True
                    if ps.match(fingerprint):
                        return True
                    self._audit.record(host, 'fingerprint mismatch', fingerprint)
                    logger.warning(
                        'Certificate pinning failed for %s: got %s, expected one of %s',
                        host, fingerprint, ps.all_pins(),
                    )
                    return False
        except Exception as exc:
            self._audit.record(host, str(exc))
            logger.warning('Certificate pinning connection error for %s: %s', host, exc)
            return False

    def validated_request(
        self,
        url: str,
        method: str = 'GET',
        headers: Optional[Dict[str, str]] = None,
        data: Optional[bytes] = None,
        timeout: int = 30,
    ) -> Optional[bytes]:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = parsed.hostname or ''
        if not self.validate(host):
            return None
        req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:
            self._audit.record(host, f'request failed: {exc}')
            logger.warning('Validated request to %s failed: %s', url, exc)
            return None

    def audit_log(self, n: int = 10) -> List[Dict[str, str]]:
        return self._audit.recent(n)

    def audit_clear(self) -> None:
        self._audit.clear()


def socket_create_connection(address, timeout):
    import socket
    return socket.create_connection(address, timeout=timeout)
