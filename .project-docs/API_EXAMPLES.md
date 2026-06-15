# 🔌 API Usage Examples Collection

This collection provides copy-pasteable, practical code snippets for utilizing the core subsystems and utility libraries inside `MAIN_CODE_PROJECT/src/`. 

---

## 📖 Table of Contents

1. [Subclassing `BaseApp`](#1-subclassing-baseapp)
2. [Circular-Free Dependency Injection (`DependencyRegistry`)](#2-circular-free-dependency-injection-dependencyregistry)
3. [Secure State Encryption (`AEADStore`) & Path Protection (`ResourceGuard`)](#3-secure-state-encryption-aeadstore--path-protection-resourceguard)
4. [Merkle Tree State Verification (`IncrementalStateReplicator`)](#4-merkle-tree-state-verification-incrementalstatereplicator)
5. [Transaction Management & Crash Recovery (`WALLogger`)](#5-transaction-management--crash-recovery-wallogger)
6. [Long-Running Pipelines with Checkpointing (`CheckpointedPipeline`)](#6-long-running-pipelines-with-checkpointing-checkpointedpipeline)
7. [Lazy Stream Processing (`LazyPipeline`)](#7-lazy-stream-processing-lazypipeline)
8. [Adaptive Batch Sizing (`AdaptiveBatchProcessor`)](#8-adaptive-batch-sizing-adaptivebatchprocessor)
9. [W3C PROV-Compliant Provenance Logging (`Provenance`)](#9-w3c-prov-compliant-provenance-logging-provenance)

---

## 1. Subclassing `BaseApp`

All executable module applications in this repository subclass [BaseApp](file:///c:/Users/Sujal/PROJECTS/NSOC_OS_5/45-Days-Python-Development-Challenge/MAIN_CODE_PROJECT/src/base_app.py). By subclassing it, you gain access to automatic configuration, output directory management, cryptographic storage, telemetry timers, and clean command-line table rendering.

```python
from typing import Any, Dict, List
from base_app import BaseApp, DataPoint

class MyCustomProcessorApp(BaseApp):
    def __init__(self) -> None:
        # 1. Initialize parent class subsystems
        super().__init__()
        self.log("MyCustomProcessorApp initialized successfully.")

    def demo_data(self) -> List[DataPoint]:
        # 2. Provide mock or initial datasets
        return [
            DataPoint(name="SensorA", value=42.0, active=True),
            DataPoint(name="SensorB", value=-12.5, active=False),
            DataPoint(name="SensorC", value=88.7, active=True)
        ]

    def process_dataset(self, items: List[Dict[str, Any] | DataPoint]) -> Dict[str, Any]:
        # 3. Ingest and aggregate data points
        active_points = []
        for item in items:
            # Reconstruct model if input was raw dict
            dp = DataPoint.from_dict(item) if isinstance(item, dict) else item
            if dp.active:
                active_points.append(dp.value)

        # Utilize BaseApp summary helper function
        summary = self.summarize_list(active_points)
        return {
            "processed_count": len(active_points),
            "summary": summary.to_dict()
        }

if __name__ == "__main__":
    app = MyCustomProcessorApp()
    # 4. Trigger lifecycle run
    app.run()
    # 5. Flush and write final state/WAL logs
    app.finalize()
```

---

## 2. Circular-Free Dependency Injection (`DependencyRegistry`)

The `DependencyRegistry` singleton avoids standard Python circular-import issues by decoupling module loading at compile-time and resolving modules using string tokens at runtime.

```python
from dependency_registry import registry
from base_app import BaseApp

# --- File A: Define and Register a Module ---
class UserServiceApp(BaseApp):
    def get_user_role(self, user_id: str) -> str:
        return "admin" if user_id == "001" else "user"

# Register the instance under a unique identifier
registry.register("user_service", UserServiceApp())

# --- File B: Resolve and Execute the Dependency ---
class OrderProcessorApp(BaseApp):
    def process_order(self, order_id: str, user_id: str) -> None:
        # Resolve user_service instance dynamically
        user_service = registry.resolve("user_service")
        if not user_service:
            raise RuntimeError("Required dependency 'user_service' is missing!")

        role = user_service.get_user_role(user_id)
        self.log(f"Processing order {order_id} for role: {role}")

if __name__ == "__main__":
    order_app = OrderProcessorApp()
    order_app.process_order(order_id="TX-9982", user_id="001")
```

---

## 3. Secure State Encryption (`AEADStore`) & Path Protection (`ResourceGuard`)

Secure local state writing is protected by `AEADStore` (Authenticated Encryption with Associated Data) and `ResourceGuard` (mitigates path traversal directory breaks).

```python
from pathlib import Path
from aead_store import AEADStore
from resource_guard import ResourceGuard

# 1. Setup resource folder boundaries
sandbox_dir = Path("outputs")
sandbox_dir.mkdir(exist_ok=True)
guard = ResourceGuard("DataGuard", sandbox_dir)

# 2. Setup crypto key configuration
# In production, load existing keys or generate a secure key
aead_key = AEADStore.generate_key() 
store = AEADStore(aead_key)

# 3. Safely format paths using the guard
unsafe_input_filename = "../../etc/passwd"  # Malicious path input
try:
    # check_path raises ValueError if the target is outside sandbox_dir
    safe_path = sandbox_dir / guard.qualify(unsafe_input_filename)
except ValueError as err:
    print(f"Path verification failed: {err}")

# Qualify a legitimate filename
safe_output_path = sandbox_dir / guard.qualify("application_state.enc")

# 4. Encrypt and persist state payload
state_payload = {"user_session": "secret_token_123", "active": True}
encrypted_bytes = store.encrypt_state(state_payload)
safe_output_path.write_bytes(encrypted_bytes)

# 5. Decrypt and load state payload
encrypted_data = safe_output_path.read_bytes()
decrypted_payload = store.decrypt_state(encrypted_data)
print(f"Decrypted Data: {decrypted_payload}")
```

---

## 4. Merkle Tree State Verification (`IncrementalStateReplicator`)

State records are structured as a cryptographic key-value store using Merkle Trees to easily verify data synchronizations and detect record modifications.

```python
from merkle_tree import IncrementalStateReplicator

# Initialize replicator
replicator = IncrementalStateReplicator()

# Initial state data
database_records = {
    "user_1": {"balance": 100},
    "user_2": {"balance": 250}
}

# 1. Create a snapshot and retrieve the Merkle Root
root_hash = replicator.snapshot(database_records)
print(f"Initial State Root Hash: {root_hash}")

# 2. Modify state records
database_records["user_1"]["balance"] = 120

# 3. Compute delta (hash differences)
new_root_hash, delta = replicator.compute_delta(database_records)
print(f"New State Root Hash: {new_root_hash}")
print(f"Computed Changes (Delta): {delta}")

# 4. Verify state records integrity
is_valid = replicator.verify_state(database_records, new_root_hash)
print(f"Is database state valid? {is_valid}")
```

---

## 5. Transaction Management & Crash Recovery (`WALLogger`)

`WALLogger` provides Write-Ahead Logging to record application state updates inside transaction segments. Replay transaction history to recover from unexpected task terminations.

```python
from pathlib import Path
from wal_logger import WALLogger

log_directory = Path("outputs/.logs")
log_directory.mkdir(parents=True, exist_ok=True)

# 1. Initialize the Write-Ahead Logger
wal = WALLogger(log_directory)

# 2. Begin a transaction
wal.begin_txn(txn_id="order_checkout_44")

# Operational parameters
database_state = {"order_id": "99", "status": "pending"}
new_status = "completed"

# 3. Log state changes BEFORE writing to actual DB/variables
wal.log_update(
    txn_id="order_checkout_44",
    key="status",
    old_value=database_state["status"],
    new_value=new_status
)

# 4. Execute state modification
database_state["status"] = new_status

# 5. Commit transaction
wal.commit_txn(txn_id="order_checkout_44")
print(f"Transaction completed. Current State: {database_state}")
```

---

## 6. Long-Running Pipelines with Checkpointing (`CheckpointedPipeline`)

For sequential operations (e.g. data processing stages), the `CheckpointedPipeline` saves execution checkpoints. If stage 3 crashes, restarting the pipeline loads the checkpoint and starts directly at stage 3.

```python
import time
from checkpoint_pipeline import CheckpointedPipeline, CheckpointStore

def ingest_stage(data: str) -> str:
    print("Executing Ingest Stage...")
    return data.upper()

def parse_stage(data: str) -> dict:
    print("Executing Parse Stage...")
    return {"raw_payload": data, "timestamp": time.time()}

def enrichment_stage(data: dict) -> dict:
    print("Executing Enrichment Stage...")
    data["enriched"] = True
    return data

if __name__ == "__main__":
    # Specify checkpoint path
    store_dir = Path("outputs/.checkpoints")
    pipeline = CheckpointedPipeline(store_dir, run_id="data_import_job_1")

    # Add processing stages in order
    pipeline.add_stage("ingest", ingest_stage)
    pipeline.add_stage("parse", parse_stage)
    pipeline.add_stage("enrich", enrichment_stage)

    # Execute from last saved checkpoint or start fresh
    result = pipeline.run("api_incoming_message_data")
    print(f"Pipeline Execution Complete: {result}")
```

---

## 7. Lazy Stream Processing (`LazyPipeline`)

For processing extremely large datasets or telemetry logs without loading the entire collection into RAM, use generator-based stream manipulations.

```python
from lazy_pipeline import LazyPipeline

# 1. Construct generator source
data_stream = (x for x in range(1, 1000000))

# 2. Instantiate pipeline and chain transformations lazily
processed_pipeline = (
    LazyPipeline(data_stream)
    .filter(lambda x: x % 2 == 0, name="FilterEvens")  # Filter: keep even numbers
    .map(lambda x: x * 10, name="ScaleByTen")          # Map: multiply by 10
)

# 3. Stream data elements lazily or collect a limited sample slice
first_five_results = []
for index, item in enumerate(processed_pipeline):
    first_five_results.append(item)
    if index >= 4:
        break

print(f"First 5 lazily processed elements: {first_five_results}")
```

---

## 8. Adaptive Batch Sizing (`AdaptiveBatchProcessor`)

For handling variable network latencies or memory spikes, the `AdaptiveBatchProcessor` automatically shrinks or expands batch sizes dynamically to maintain peak performance.

```python
import time
from adaptive_batch import AdaptiveBatchProcessor

def slow_external_api_uploader(batch: list) -> list:
    """Mock database or API processing function."""
    # Simulation: latency increases if batch size is too large
    latency = len(batch) * 0.05
    time.sleep(latency)
    return [item * 2 for item in batch]

# Instantiate processor with task handler
processor = AdaptiveBatchProcessor(slow_external_api_uploader)

large_list_of_tasks = list(range(1000))

# Automatically adjusts batches based on processing timing history
log_results = processor.process(large_list_of_tasks)
print(f"Processed {len(log_results)} elements. Current optimal batch size: {processor.current}")
```

---

## 9. W3C PROV-Compliant Provenance Logging (`Provenance`)

For enterprise auditing, track which users, processes, and systems modified files or generated datasets using the standard W3C Provenance specification.

```python
from provenance import ProvenanceTracker

tracker = ProvenanceTracker()

# 1. Register Agents (who performed the action)
user_agent = tracker.agent(name="admin_user", role="DataEngineer")

# 2. Register Activities (actions executed)
parse_activity = tracker.activity(name="ParseLogs", duration=1.25)

# 3. Register Entities (inputs & outputs)
source_file = tracker.entity(name="raw_logs.csv", path="outputs/raw_logs.csv")
output_db = tracker.entity(name="db_records.json", path="outputs/db_records.json")

# 4. Draw lineage derivations
tracker.derivation(derived=output_db, source=source_file, activity=parse_activity)

# 5. Export structural provenance audit logs
tracker.export_json("outputs/provenance_audit.json")
print("Provenance graph saved. Lineage query details:")
print(tracker.lineage(output_db))
```
