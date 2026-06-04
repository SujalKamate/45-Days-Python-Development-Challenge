"""Adaptive password hashing via PBKDF2-HMAC-SHA256 with configurable work factor.

Usage::

    from .password_hasher import hash_password, verify_password

    hashed = hash_password('my_password')
    assert verify_password('my_password', hashed)
"""

import hashlib
import os
import base64

_PBKDF2_ITERATIONS = int(os.getenv('PBKDF2_ITERATIONS', '600000'))
_ALGORITHM = 'pbkdf2_sha256'


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, _PBKDF2_ITERATIONS)
    b64_salt = base64.b64encode(salt).decode('ascii')
    b64_hash = base64.b64encode(dk).decode('ascii')
    return f'{_ALGORITHM}:{_PBKDF2_ITERATIONS}:{b64_salt}:{b64_hash}'


def verify_password(password: str, stored: str) -> bool:
    try:
        parts = stored.split(':')
        if parts[0] != _ALGORITHM:
            return False
        iterations = int(parts[1])
        salt = base64.b64decode(parts[2])
        dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
        expected = base64.b64encode(dk).decode('ascii')
        return expected == parts[3]
    except (ValueError, IndexError, TypeError):
        return False
