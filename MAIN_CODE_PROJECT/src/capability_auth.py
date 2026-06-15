"""Capability-based authorization tokens with delegation and attenuation support."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import datetime
import hashlib
import hmac
import json
import os
import threading
import time


def _sign(key: bytes, payload: bytes) -> str:
    return hmac.new(key, payload, 'sha256').hexdigest()


def _make_id() -> str:
    return os.urandom(16).hex()


class Capability:
    """An unforgeable capability token with optional delegation chain."""

    def __init__(
        self,
        object_id: str,
        actions: Set[str],
        issuer: str,
        expiry: Optional[datetime.datetime] = None,
        caveats: Optional[List[Dict[str, Any]]] = None,
        parent_id: Optional[str] = None,
    ) -> None:
        self.id = _make_id()
        self.object_id = object_id
        self.actions = actions
        self.issuer = issuer
        self.expiry = expiry
        self.caveats = caveats or []
        self.parent_id = parent_id
        self._issued_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'object_id': self.object_id,
            'actions': sorted(self.actions),
            'issuer': self.issuer,
            'expiry': self.expiry.isoformat() if self.expiry else None,
            'caveats': self.caveats,
            'parent_id': self.parent_id,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> Capability:
        cap = Capability(
            object_id=d['object_id'],
            actions=set(d['actions']),
            issuer=d['issuer'],
            expiry=datetime.datetime.fromisoformat(d['expiry']) if d.get('expiry') else None,
            caveats=d.get('caveats', []),
            parent_id=d.get('parent_id'),
        )
        cap.id = d['id']
        return cap


class CapabilityToken:
    """Signed capability token — HMAC-sealed for tamper-proof verification."""

    def __init__(self, capability: Capability, signing_key: bytes) -> None:
        self._cap = capability
        self._key = signing_key
        payload = json.dumps(capability.to_dict(), sort_keys=True, default=str).encode('utf-8')
        self._signature = _sign(signing_key, payload)

    @property
    def capability(self) -> Capability:
        return self._cap

    def to_dict(self) -> Dict[str, Any]:
        return {
            'capability': self._cap.to_dict(),
            'signature': self._signature,
        }

    def serialize(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, default=str)

    @staticmethod
    def deserialize(data: str, signing_key: bytes) -> Optional[CapabilityToken]:
        try:
            d = json.loads(data)
            cap = Capability.from_dict(d['capability'])
            sig = d['signature']
            expected = _sign(signing_key, json.dumps(cap.to_dict(), sort_keys=True, default=str).encode('utf-8'))
            if not hmac.compare_digest(sig, expected):
                return None
            return CapabilityToken(cap, signing_key)
        except Exception:
            return None


class CapabilityManager:
    """Issues, validates, delegates, and attenuates capability tokens."""

    def __init__(self, signing_key: Optional[bytes] = None) -> None:
        self._key = signing_key or os.urandom(32)
        self._revoked: Set[str] = set()
        self._lock = threading.Lock()
        self._audit: List[Dict[str, Any]] = []

    def issue(
        self,
        object_id: str,
        actions: Set[str],
        issuer: str,
        expiry: Optional[datetime.datetime] = None,
        caveats: Optional[List[Dict[str, Any]]] = None,
    ) -> CapabilityToken:
        cap = Capability(object_id, actions, issuer, expiry, caveats)
        token = CapabilityToken(cap, self._key)
        self._audit_log('issue', cap.id, object_id, issuer)
        return token

    def delegate(
        self,
        token: CapabilityToken,
        issuer: str,
        restricted_actions: Optional[Set[str]] = None,
        additional_caveats: Optional[List[Dict[str, Any]]] = None,
        expiry: Optional[datetime.datetime] = None,
    ) -> Optional[CapabilityToken]:
        if not self.validate(token):
            return None
        parent = token.capability
        actions = restricted_actions if restricted_actions is not None else set(parent.actions)
        actions &= parent.actions
        if not actions:
            return None
        caveats = list(parent.caveats)
        if additional_caveats:
            caveats.extend(additional_caveats)
        child = Capability(
            object_id=parent.object_id,
            actions=actions,
            issuer=issuer,
            expiry=expiry or parent.expiry,
            caveats=caveats,
            parent_id=parent.id,
        )
        child_token = CapabilityToken(child, self._key)
        self._audit_log('delegate', child.id, parent.object_id, issuer, parent.id)
        return child_token

    def attenuate(
        self,
        token: CapabilityToken,
        issuer: str,
        remove_actions: Optional[Set[str]] = None,
        add_caveats: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[CapabilityToken]:
        parent = token.capability
        actions = set(parent.actions)
        if remove_actions:
            actions -= remove_actions
        return self.delegate(token, issuer, restricted_actions=actions, additional_caveats=add_caveats)

    def validate(self, token: CapabilityToken) -> bool:
        cap = token.capability
        if cap.id in self._revoked:
            self._audit_log('deny_revoked', cap.id, cap.object_id, cap.issuer)
            return False
        if cap.expiry and datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) > cap.expiry:
            self._audit_log('deny_expired', cap.id, cap.object_id, cap.issuer)
            return False
        for caveat in cap.caveats:
            if not self._check_caveat(caveat):
                self._audit_log('deny_caveat', cap.id, cap.object_id, cap.issuer, detail=str(caveat))
                return False
        return True

    def check(self, token: CapabilityToken, object_id: str, action: str) -> bool:
        if not self.validate(token):
            return False
        cap = token.capability
        if cap.object_id != object_id:
            return False
        if action not in cap.actions:
            return False
        self._audit_log('check_pass', cap.id, object_id, cap.issuer, action=action)
        return True

    def revoke(self, token: CapabilityToken) -> None:
        with self._lock:
            self._revoked.add(token.capability.id)
        self._audit_log('revoke', token.capability.id, token.capability.object_id, token.capability.issuer)

    def revoke_by_id(self, cap_id: str) -> None:
        with self._lock:
            self._revoked.add(cap_id)

    def _check_caveat(self, caveat: Dict[str, Any]) -> bool:
        typ = caveat.get('type', '')
        if typ == 'before':
            before = caveat.get('time', '')
            if before:
                try:
                    limit = datetime.datetime.fromisoformat(before)
                    if datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) > limit:
                        return False
                except ValueError:
                    return False
        elif typ == 'ip_allow':
            return True
        return True

    def _audit_log(self, event: str, cap_id: str, obj: str, issuer: str, parent_id: Optional[str] = None, action: Optional[str] = None, detail: Optional[str] = None) -> None:
        entry: Dict[str, Any] = {
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'event': event,
            'capability_id': cap_id,
            'object_id': obj,
            'issuer': issuer,
        }
        if parent_id:
            entry['parent_id'] = parent_id
        if action:
            entry['action'] = action
        if detail:
            entry['detail'] = detail
        with self._lock:
            self._audit.append(entry)

    def audit_log(self, n: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._audit[-n:])

    def audit_clear(self) -> None:
        with self._lock:
            self._audit.clear()

    def export_key(self, path: str) -> None:
        with open(path, 'wb') as f:
            f.write(self._key.hex().encode('utf-8'))

    @staticmethod
    def load_key(path: str) -> bytes:
        with open(path, 'rb') as f:
            return bytes.fromhex(f.read().decode('utf-8').strip())
