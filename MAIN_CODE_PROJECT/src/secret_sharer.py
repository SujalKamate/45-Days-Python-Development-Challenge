"""Threshold secret sharing (Shamir's Secret Sharing) for secure key distribution."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import hashlib
import json
import os
import threading


_PRIME = (1 << 127) - 1


def _mod(a: int, b: int = _PRIME) -> int:
    return ((a % b) + b) % b


def _eval_poly(coeffs: List[int], x: int) -> int:
    result = 0
    for c in reversed(coeffs):
        result = _mod(result * x + c)
    return result


def _lagrange_interpolate(shares: List[Tuple[int, int]], x: int) -> int:
    result = 0
    for i, (xi, yi) in enumerate(shares):
        num = 1
        den = 1
        for j, (xj, _) in enumerate(shares):
            if i == j:
                continue
            num = _mod(num * _mod(x - xj))
            den = _mod(den * _mod(xi - xj))
        result = _mod(result + yi * _mod(num * pow(den, _PRIME - 2, _PRIME)))
    return result


def _int_from_bytes(data: bytes) -> int:
    return int.from_bytes(data, 'big')


def _int_to_bytes(value: int, length: int) -> bytes:
    return value.to_bytes(length, 'big')


class SecretSharer:
    """Shamir's Secret Sharing — split a secret into N shares, require K to reconstruct."""

    def __init__(self, threshold: int = 3, total_shares: int = 5) -> None:
        if threshold > total_shares:
            raise ValueError('threshold cannot exceed total_shares')
        self._threshold = threshold
        self._total = total_shares

    def split(self, secret: bytes) -> List[Tuple[int, bytes]]:
        secret_int = _int_from_bytes(secret)
        if secret_int >= _PRIME:
            raise ValueError('secret too large for prime field')
        coeffs = [secret_int]
        for _ in range(1, self._threshold):
            coeffs.append(_mod(_int_from_bytes(os.urandom(16))))
        shares: List[Tuple[int, bytes]] = []
        for i in range(1, self._total + 1):
            val = _eval_poly(coeffs, i)
            shares.append((i, val.to_bytes(16, 'big')))
        return shares

    def reconstruct(self, shares: List[Tuple[int, bytes]]) -> bytes:
        if len(shares) < self._threshold:
            raise ValueError(f'need at least {self._threshold} shares, got {len(shares)}')
        int_shares = [(i, _int_from_bytes(v)) for i, v in shares[:self._threshold]]
        secret_int = _lagrange_interpolate(int_shares, 0)
        byte_len = len(shares[0][1])
        return secret_int.to_bytes(byte_len, 'big')


class ShareStore:
    """Manages shares across multiple storage locations for resilience."""

    def __init__(self, base_dir: str = '.shares') -> None:
        self._base = base_dir
        self._lock = threading.Lock()

    def save_shares(self, label: str, shares: List[Tuple[int, bytes]]) -> List[str]:
        import os as _os
        paths: List[str] = []
        for idx, value in shares:
            share_dir = f'{self._base}/{label}/share_{idx}'
            os.makedirs(share_dir, exist_ok=True)
            path = f'{share_dir}/secret.bin'
            with open(path, 'wb') as f:
                f.write(value)
            paths.append(path)
        return paths

    def load_shares(self, label: str, indices: List[int]) -> List[Tuple[int, bytes]]:
        shares: List[Tuple[int, bytes]] = []
        for idx in indices:
            path = f'{self._base}/{label}/share_{idx}/secret.bin'
            if os.path.exists(path):
                with open(path, 'rb') as f:
                    shares.append((idx, f.read()))
        return shares

    def list_labels(self) -> List[str]:
        if not os.path.isdir(self._base):
            return []
        return [d for d in os.listdir(self._base)
                if os.path.isdir(f'{self._base}/{d}')]


class RotatingKeyManager:
    """Manages periodic share rotation without exposing the original secret."""

    def __init__(self, threshold: int = 3, total_shares: int = 5) -> None:
        self._sharer = SecretSharer(threshold, total_shares)
        self._store = ShareStore()

    def create(self, label: str, secret: bytes) -> List[str]:
        shares = self._sharer.split(secret)
        return self._store.save_shares(label, shares)

    def recover(self, label: str, share_indices: List[int]) -> bytes:
        shares = self._store.load_shares(label, share_indices)
        return self._sharer.reconstruct(shares)

    def rotate(self, label: str, share_indices: List[int]) -> List[str]:
        secret = self.recover(label, share_indices)
        import shutil
        import os as _os
        share_dir = f'{self._store._base}/{label}'
        if _os.path.isdir(share_dir):
            shutil.rmtree(share_dir)
        return self.create(label, secret)
