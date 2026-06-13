"""AEAD encryption (AES-256-GCM) for authenticated state persistence with integrity verification."""

from __future__ import annotations

from typing import Any, Dict, Optional
import hashlib
import json
import os
import threading


_NONCE_SIZE = 12
_TAG_SIZE = 16
_KEY_SIZE = 32


def generate_key() -> bytes:
    return os.urandom(_KEY_SIZE)


def _derive_key(master_key: bytes, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac('sha256', master_key, salt, 100000, dklen=_KEY_SIZE)


class AEADCipher:
    """AES-256-GCM encrypt/decrypt with associated data for tamper detection."""

    @staticmethod
    def encrypt(plaintext: bytes, key: bytes, aad: bytes = b'') -> bytes:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        nonce = os.urandom(_NONCE_SIZE)
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, aad)
        return nonce + ciphertext

    @staticmethod
    def decrypt(payload: bytes, key: bytes, aad: bytes = b'') -> bytes:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        if len(payload) < _NONCE_SIZE + _TAG_SIZE:
            raise ValueError('truncated ciphertext')
        nonce = payload[:_NONCE_SIZE]
        ciphertext = payload[_NONCE_SIZE:]
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, aad)


class AEADStore:
    """Encrypted, integrity-protected state persistence using AEAD."""

    def __init__(self, master_key: Optional[bytes] = None) -> None:
        self._master_key = master_key or generate_key()
        self._lock = threading.Lock()

    @property
    def key(self) -> bytes:
        return self._master_key

    def encrypt_state(self, data: Dict[str, Any], salt: Optional[bytes] = None) -> bytes:
        salt = salt or os.urandom(16)
        key = _derive_key(self._master_key, salt)
        plaintext = json.dumps(data, sort_keys=True, default=str).encode('utf-8')
        ciphertext = AEADCipher.encrypt(plaintext, key, aad=salt)
        envelope = {
            'salt': salt.hex(),
            'ciphertext': ciphertext.hex(),
            'key_hash': hashlib.sha256(key).hexdigest()[:16],
        }
        return json.dumps(envelope).encode('utf-8')

    def decrypt_state(self, payload: bytes) -> Dict[str, Any]:
        envelope = json.loads(payload.decode('utf-8'))
        salt = bytes.fromhex(envelope['salt'])
        ciphertext = bytes.fromhex(envelope['ciphertext'])
        key = _derive_key(self._master_key, salt)
        expected_hash = envelope.get('key_hash', '')
        if expected_hash:
            actual_hash = hashlib.sha256(key).hexdigest()[:16]
            if actual_hash != expected_hash:
                raise ValueError('key hash mismatch — tampering detected')
        plaintext = AEADCipher.decrypt(ciphertext, key, aad=salt)
        return json.loads(plaintext.decode('utf-8'))

    def rotate_key(self, payload: bytes, new_key: bytes) -> bytes:
        data = self.decrypt_state(payload)
        old_key = self._master_key
        self._master_key = new_key
        result = self.encrypt_state(data)
        self._master_key = old_key
        return result

    def export_key(self, path: str) -> None:
        with open(path, 'wb') as f:
            f.write(self._master_key.hex().encode('utf-8'))

    @staticmethod
    def load_key(path: str) -> bytes:
        with open(path, 'rb') as f:
            return bytes.fromhex(f.read().decode('utf-8').strip())
