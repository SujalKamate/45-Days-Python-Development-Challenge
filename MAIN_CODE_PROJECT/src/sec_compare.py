"""Constant-time comparison utilities for timing-attack-resistant sensitive operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union
import hashlib
import hmac


def compare_bytes(a: bytes, b: bytes) -> bool:
    if not isinstance(a, bytes) or not isinstance(b, bytes):
        return False
    return hmac.compare_digest(a, b)


def compare_str(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode('utf-8'), b.encode('utf-8'))


def compare_int(a: int, b: int) -> bool:
    return hmac.compare_digest(str(a).encode('utf-8'), str(b).encode('utf-8'))


def constant_time_eq(a: Any, b: Any) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, bytes):
        return compare_bytes(a, b)
    if isinstance(a, str):
        return compare_str(a, b)
    if isinstance(a, int):
        return compare_int(a, b)
    return a == b


def constant_time_select(condition: bool, true_val: bytes, false_val: bytes) -> bytes:
    mask = b'\xff' if condition else b'\x00'
    result = bytearray(len(true_val))
    for i in range(len(true_val)):
        result[i] = (true_val[i] & mask[i % len(mask)]) | (false_val[i] & ~mask[i % len(mask)])
    return bytes(result)


def constant_time_cmp(result: bool) -> bytes:
    return b'\x01' if result else b'\x00'


def verify_checksum(data: bytes, expected: bytes) -> bool:
    computed = hashlib.sha256(data).digest()
    return hmac.compare_digest(computed, expected)


def verify_hmac(key: bytes, message: bytes, expected_mac: bytes) -> bool:
    computed = hmac.digest(key, message, 'sha256')
    return hmac.compare_digest(computed, expected_mac)


class SecureCompare:
    """Collection of constant-time comparison methods for security-sensitive validation."""

    @staticmethod
    def bytes_eq(a: bytes, b: bytes) -> bool:
        return compare_bytes(a, b)

    @staticmethod
    def str_eq(a: str, b: str) -> bool:
        return compare_str(a, b)

    @staticmethod
    def int_eq(a: int, b: int) -> bool:
        return compare_int(a, b)

    @staticmethod
    def dict_eq(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
        if set(a.keys()) != set(b.keys()):
            return False
        for k in a:
            sk = str(k)
            if isinstance(a[k], dict):
                if not SecureCompare.dict_eq(a[k], b[k]):
                    return False
            elif isinstance(a[k], bytes):
                if not compare_bytes(a[k], b.get(k, b'')):
                    return False
            elif isinstance(a[k], str):
                if not compare_str(a[k], str(b.get(k, ''))):
                    return False
            else:
                if not constant_time_eq(a[k], b[k]):
                    return False
        return True

    @staticmethod
    def checksum(data: bytes) -> bytes:
        return hashlib.sha256(data).digest()

    @staticmethod
    def verify_checksum(data: bytes, expected: bytes) -> bool:
        return verify_checksum(data, expected)

    @staticmethod
    def hmac_sign(key: bytes, message: bytes) -> bytes:
        return hmac.digest(key, message, 'sha256')

    @staticmethod
    def verify_hmac(key: bytes, message: bytes, expected_mac: bytes) -> bool:
        return verify_hmac(key, message, expected_mac)
