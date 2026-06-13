"""Merkle tree for incremental state replication with cryptographic integrity verification."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import hashlib
import json


class MerkleNode:
    __slots__ = ('hash', 'left', 'right', 'key')

    def __init__(self, hash_value: str, left: Optional[MerkleNode] = None,
                 right: Optional[MerkleNode] = None, key: Optional[str] = None) -> None:
        self.hash = hash_value
        self.left = left
        self.right = right
        self.key = key


class MerkleTree:
    """Merkle tree that maps state key-value pairs into a cryptographic hash tree.

    Leaves are sorted by key for deterministic root computation.
    """

    def __init__(self, data: Optional[Dict[str, Any]] = None) -> None:
        self._nodes: Dict[str, MerkleNode] = {}
        self._root: Optional[MerkleNode] = None
        if data is not None:
            self.build(data)

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode('utf-8')).hexdigest()

    def build(self, data: Dict[str, Any]) -> str:
        sorted_keys = sorted(data.keys())
        if not sorted_keys:
            empty_hash = self._hash('')
            self._root = MerkleNode(empty_hash)
            return empty_hash

        leaves: List[MerkleNode] = []
        for key in sorted_keys:
            leaf_data = json.dumps({key: data[key]}, sort_keys=True, default=str)
            leaf_hash = self._hash(leaf_data)
            leaf = MerkleNode(leaf_hash, key=key)
            self._nodes[key] = leaf
            leaves.append(leaf)

        self._root = self._build_internal(leaves)
        return self._root.hash

    def _build_internal(self, nodes: List[MerkleNode]) -> MerkleNode:
        if len(nodes) == 1:
            return nodes[0]

        next_level: List[MerkleNode] = []
        for i in range(0, len(nodes), 2):
            if i + 1 < len(nodes):
                combined = nodes[i].hash + nodes[i + 1].hash
                parent = MerkleNode(self._hash(combined), left=nodes[i], right=nodes[i + 1])
            else:
                parent = nodes[i]
            next_level.append(parent)

        return self._build_internal(next_level)

    @property
    def root_hash(self) -> Optional[str]:
        return self._root.hash if self._root else None

    def get_proof(self, key: str) -> List[Tuple[str, bool]]:
        if key not in self._nodes:
            return []

        sorted_keys = sorted(self._nodes.keys())
        proof: List[Tuple[str, bool]] = []
        target_idx = sorted_keys.index(key)

        level_nodes = [self._nodes[k] for k in sorted_keys]
        level_indices = list(range(len(level_nodes)))

        while len(level_nodes) > 1:
            next_nodes: List[MerkleNode] = []
            next_indices: List[int] = []

            for i in range(0, len(level_nodes), 2):
                if i + 1 < len(level_nodes):
                    if level_indices[i] == target_idx or level_indices[i + 1] == target_idx:
                        if level_indices[i] == target_idx:
                            proof.append((level_nodes[i + 1].hash, False))
                        else:
                            proof.append((level_nodes[i].hash, True))

                    combined = level_nodes[i].hash + level_nodes[i + 1].hash
                    parent = MerkleNode(self._hash(combined))
                    next_nodes.append(parent)
                    next_indices.append(
                        level_indices[i] if level_indices[i] == target_idx
                        else level_indices[i + 1]
                    )
                else:
                    next_nodes.append(level_nodes[i])
                    next_indices.append(level_indices[i])

            level_nodes = next_nodes
            level_indices = next_indices
            target_idx = next_indices[0] if next_indices else -1

        return proof

    @staticmethod
    def verify_proof(root_hash: str, key: str, value: Any, proof: List[Tuple[str, bool]]) -> bool:
        leaf_data = json.dumps({key: value}, sort_keys=True, default=str)
        current_hash = hashlib.sha256(leaf_data.encode('utf-8')).hexdigest()

        for sibling_hash, is_left in proof:
            combined = sibling_hash + current_hash if is_left else current_hash + sibling_hash
            current_hash = hashlib.sha256(combined.encode('utf-8')).hexdigest()

        return current_hash == root_hash

    def compute_root(self, data: Dict[str, Any]) -> str:
        return self.__class__(data).root_hash or ''


class IncrementalStateReplicator:
    """Supports incremental state synchronization using Merkle tree verification.

    Tracks the last-known Merkle root and computes deltas between state snapshots.
    """

    def __init__(self) -> None:
        self._last_root: Optional[str] = None
        self._last_data: Dict[str, Any] = {}
        self._merkle = MerkleTree()

    @property
    def last_root(self) -> Optional[str]:
        return self._last_root

    def snapshot(self, data: Dict[str, Any]) -> str:
        root = self._merkle.compute_root(data)
        self._last_root = root
        self._last_data = dict(data)
        return root

    def compute_delta(self, new_data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        new_root = self._merkle.compute_root(new_data)

        if self._last_root == new_root:
            return new_root, {}

        delta: Dict[str, Any] = {}
        all_keys = set(self._last_data.keys()) | set(new_data.keys())
        for key in sorted(all_keys):
            old_val = self._last_data.get(key)
            new_val = new_data.get(key)
            if old_val != new_val:
                if key in new_data:
                    delta[key] = new_val
                else:
                    delta[key] = None

        return new_root, delta

    def apply_delta(self, base_data: Dict[str, Any], delta: Dict[str, Any],
                    expected_root: Optional[str] = None) -> Dict[str, Any]:
        result = dict(base_data)
        for key, value in delta.items():
            if value is None:
                result.pop(key, None)
            else:
                result[key] = value

        if expected_root is not None:
            computed_root = self._merkle.compute_root(result)
            if computed_root != expected_root:
                raise ValueError(
                    f'Integrity mismatch: expected root {expected_root}, got {computed_root}'
                )

        return result

    def verify_state(self, data: Dict[str, Any], root_hash: str) -> bool:
        return self._merkle.compute_root(data) == root_hash
