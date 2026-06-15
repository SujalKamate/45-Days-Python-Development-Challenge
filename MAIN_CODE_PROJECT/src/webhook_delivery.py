"""Event-driven webhook delivery framework for automated post-execution notifications."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple
import datetime
import hashlib
import hmac
import json
import os
import threading
import time
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


_MAX_RETRIES = 5
_BACKOFF_BASE_S = 1.0
_BACKOFF_MAX_S = 60.0
_DEFAULT_TIMEOUT_S = 10.0
_IDEMPOTENCY_TTL_S = 3600.0


class WebhookPayload:
    """Payload with HMAC-SHA256 signature for delivery verification."""

    def __init__(self, event_id: str, event_type: str, data: Any,
                 timestamp: Optional[str] = None) -> None:
        self.event_id = event_id
        self.event_type = event_type
        self.data = data
        self.timestamp = timestamp or datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.signature = ''

    def sign(self, secret: str) -> str:
        raw = json.dumps(self.to_dict(), separators=(',', ':'), sort_keys=True)
        self.signature = hmac.new(
            secret.encode('utf-8'), raw.encode('utf-8'), hashlib.sha256
        ).hexdigest()
        return self.signature

    def verify(self, secret: str) -> bool:
        if not self.signature:
            return False
        expected = hmac.new(
            secret.encode('utf-8'),
            json.dumps(self.to_dict(exclude_signature=True), separators=(',', ':'), sort_keys=True).encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(self.signature, expected)

    def to_dict(self, exclude_signature: bool = False) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            'event_id': self.event_id,
            'event_type': self.event_type,
            'data': self.data,
            'timestamp': self.timestamp,
        }
        if not exclude_signature:
            d['signature'] = self.signature
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> WebhookPayload:
        p = WebhookPayload(
            event_id=d.get('event_id', uuid.uuid4().hex),
            event_type=d.get('event_type', ''),
            data=d.get('data', {}),
            timestamp=d.get('timestamp', ''),
        )
        p.signature = d.get('signature', '')
        return p


class WebhookEndpoint:
    """A registered webhook endpoint with delivery configuration."""

    def __init__(self, url: str, secret: str = '',
                 headers: Optional[Dict[str, str]] = None,
                 max_retries: int = _MAX_RETRIES,
                 timeout_s: float = _DEFAULT_TIMEOUT_S,
                 event_types: Optional[List[str]] = None,
                 label: str = '') -> None:
        self.id = uuid.uuid4().hex[:12]
        self.url = url
        self.secret = secret
        self.headers = headers or {}
        self.max_retries = max_retries
        self.timeout_s = timeout_s
        self.event_types = event_types
        self.label = label
        self.active = True
        self.created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def matches_event(self, event_type: str) -> bool:
        if self.event_types is None:
            return True
        return event_type in self.event_types

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'url': self.url,
            'secret': '<redacted>' if self.secret else '',
            'headers': self.headers,
            'max_retries': self.max_retries,
            'timeout_s': self.timeout_s,
            'event_types': self.event_types,
            'label': self.label,
            'active': self.active,
            'created_at': self.created_at,
        }


class DeliveryRecord:
    """Record of a single delivery attempt."""

    def __init__(self, endpoint_id: str, event_id: str, status: str = 'pending',
                 response_code: int = 0, error: str = '',
                 attempt: int = 0) -> None:
        self.id = uuid.uuid4().hex[:16]
        self.endpoint_id = endpoint_id
        self.event_id = event_id
        self.status = status
        self.response_code = response_code
        self.error = error
        self.attempt = attempt
        self.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'endpoint_id': self.endpoint_id,
            'event_id': self.event_id,
            'status': self.status,
            'response_code': self.response_code,
            'error': self.error,
            'attempt': self.attempt,
            'timestamp': self.timestamp,
        }


class IdempotencyStore:
    """Idempotency key store to prevent duplicate event processing."""

    def __init__(self) -> None:
        self._store: Dict[str, float] = {}

    def is_processed(self, event_id: str) -> bool:
        now = time.time()
        self._store = {k: v for k, v in self._store.items() if now - v < _IDEMPOTENCY_TTL_S}
        return event_id in self._store

    def mark_processed(self, event_id: str) -> None:
        self._store[event_id] = time.time()


class WebhookDispatcher:
    """Dispatches webhook payloads with retry, backoff, and idempotency."""

    def __init__(self, idempotency_store: IdempotencyStore) -> None:
        self._idempotency = idempotency_store

    def deliver(self, endpoint: WebhookEndpoint, payload: WebhookPayload,
                on_result: Optional[Callable[[DeliveryRecord], None]] = None) -> DeliveryRecord:
        if not endpoint.active:
            return DeliveryRecord(endpoint.id, payload.event_id, 'skipped', error='endpoint inactive')

        if self._idempotency.is_processed(payload.event_id):
            return DeliveryRecord(endpoint.id, payload.event_id, 'idempotent_skip')

        payload.sign(endpoint.secret)
        body = json.dumps(payload.to_dict()).encode('utf-8')
        final_record: Optional[DeliveryRecord] = None

        for attempt in range(1, endpoint.max_retries + 1):
            try:
                req = Request(endpoint.url, data=body, method='POST')
                req.add_header('Content-Type', 'application/json')
                req.add_header('X-Event-Id', payload.event_id)
                req.add_header('X-Event-Type', payload.event_type)
                req.add_header('X-Signature-256', payload.signature)
                for k, v in endpoint.headers.items():
                    req.add_header(k, v)

                with urlopen(req, timeout=endpoint.timeout_s) as resp:
                    status_code = resp.status
                    record = DeliveryRecord(
                        endpoint.id, payload.event_id, 'delivered',
                        response_code=status_code, attempt=attempt,
                    )

                final_record = record
                if on_result:
                    on_result(record)
                self._idempotency.mark_processed(payload.event_id)
                return record

            except (HTTPError, URLError, OSError) as e:
                code = getattr(e, 'code', 0) if isinstance(e, HTTPError) else 0
                status = 'failed'
                if attempt < endpoint.max_retries:
                    backoff = min(_BACKOFF_BASE_S * (2 ** (attempt - 1)), _BACKOFF_MAX_S)
                    time.sleep(backoff)
                    status = 'retrying'
                else:
                    status = 'failed'

                record = DeliveryRecord(
                    endpoint.id, payload.event_id, status,
                    response_code=code, error=str(e), attempt=attempt,
                )
                final_record = record
                if on_result:
                    on_result(record)

        if final_record:
            return final_record
        return DeliveryRecord(endpoint.id, payload.event_id, 'failed', error='unknown')


class WebhookRegistry:
    """Manages webhook endpoint registration, delivery history, and audit."""

    def __init__(self) -> None:
        self._endpoints: Dict[str, WebhookEndpoint] = {}
        self._history: List[DeliveryRecord] = []
        self._lock = threading.Lock()

    def register(self, endpoint: WebhookEndpoint) -> str:
        with self._lock:
            self._endpoints[endpoint.id] = endpoint
        return endpoint.id

    def unregister(self, endpoint_id: str) -> bool:
        with self._lock:
            ep = self._endpoints.pop(endpoint_id, None)
            if ep:
                ep.active = False
                return True
            return False

    def get_endpoint(self, endpoint_id: str) -> Optional[WebhookEndpoint]:
        with self._lock:
            return self._endpoints.get(endpoint_id)

    def list_endpoints(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [ep.to_dict() for ep in self._endpoints.values()]

    def record_delivery(self, record: DeliveryRecord) -> None:
        with self._lock:
            self._history.append(record)

    def delivery_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            return [r.to_dict() for r in self._history[-limit:]]

    def delivery_stats(self) -> Dict[str, int]:
        with self._lock:
            stats: Dict[str, int] = {}
            for r in self._history:
                stats[r.status] = stats.get(r.status, 0) + 1
            return stats


class WebhookDeliveryEngine:
    """Top-level webhook delivery framework."""

    def __init__(self) -> None:
        self._registry = WebhookRegistry()
        self._idempotency = IdempotencyStore()
        self._dispatcher = WebhookDispatcher(self._idempotency)

    @property
    def registry(self) -> WebhookRegistry:
        return self._registry

    def register_endpoint(self, url: str, secret: str = '',
                          headers: Optional[Dict[str, str]] = None,
                          max_retries: int = _MAX_RETRIES,
                          timeout_s: float = _DEFAULT_TIMEOUT_S,
                          event_types: Optional[List[str]] = None,
                          label: str = '') -> str:
        ep = WebhookEndpoint(url, secret, headers, max_retries, timeout_s, event_types, label)
        return self._registry.register(ep)

    def unregister_endpoint(self, endpoint_id: str) -> bool:
        return self._registry.unregister(endpoint_id)

    def list_endpoints(self) -> List[Dict[str, Any]]:
        return self._registry.list_endpoints()

    def deliver(self, event_type: str, data: Any,
                endpoint_id: Optional[str] = None) -> List[DeliveryRecord]:
        event_id = uuid.uuid4().hex[:16]
        payload = WebhookPayload(event_id, event_type, data)
        results: List[DeliveryRecord] = []

        endpoints = [self._registry.get_endpoint(endpoint_id)] if endpoint_id else self._registry.list_endpoints_raw()

        for ep in endpoints:
            if ep is None:
                continue
            if not ep.matches_event(event_type):
                continue

            def _on_result(record: DeliveryRecord) -> None:
                self._registry.record_delivery(record)

            record = self._dispatcher.deliver(ep, payload, on_result=_on_result)
            results.append(record)

        return results

    def delivery_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._registry.delivery_history(limit)

    def delivery_stats(self) -> Dict[str, int]:
        return self._registry.delivery_stats()

    def summary(self) -> Dict[str, Any]:
        return {
            'endpoints': len(self._registry.list_endpoints()),
            'deliveries': len(self._registry.delivery_history(limit=999999)),
            'stats': self.delivery_stats(),
        }

    def report_text(self) -> str:
        s = self.summary()
        return (
            f'Webhook Delivery Engine\n'
            f'  Registered endpoints: {s["endpoints"]}\n'
            f'  Total delivery records: {s["deliveries"]}\n'
            f'  Status breakdown: {s["stats"]}'
        )

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        sp = os.path.join(dir, 'webhook_delivery.json')
        with open(sp, 'w') as f:
            json.dump(self.summary(), f, indent=2)
        paths.append(sp)
        hp = os.path.join(dir, 'webhook_history.json')
        with open(hp, 'w') as f:
            json.dump(self.delivery_history(limit=500), f, indent=2)
        paths.append(hp)
        return paths
