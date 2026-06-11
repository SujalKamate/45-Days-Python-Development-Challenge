"""
Multi-Threaded File Downloader Simulator with Progress Tracking and Locks
Simulates concurrent file downloads using threading, with progress bars and timing.
"""

import threading
import time
import random
import sys
from collections import defaultdict
from datetime import datetime


# ── Shared State (thread-safe) ────────────────────────────────────────────────
class DownloadManager:
    def __init__(self):
        self._lock          = threading.Lock()
        self._progress      = {}    # filename -> (downloaded_bytes, total_bytes, status)
        self._log           = []
        self._total_bytes   = 0
        self._done_bytes    = 0

    def register(self, filename, total_bytes):
        with self._lock:
            self._progress[filename] = {
                "total":      total_bytes,
                "downloaded": 0,
                "status":     "queued",
                "speed":      0,
                "start_time": None,
                "end_time":   None,
            }
            self._total_bytes += total_bytes

    def update(self, filename, chunk_bytes, status="downloading"):
        with self._lock:
            info = self._progress[filename]
            info["downloaded"] = min(info["downloaded"] + chunk_bytes, info["total"])
            info["status"]     = status
            self._done_bytes   += chunk_bytes

    def start_file(self, filename):
        with self._lock:
            self._progress[filename]["status"]     = "downloading"
            self._progress[filename]["start_time"] = time.time()

    def finish_file(self, filename, success=True):
        with self._lock:
            info = self._progress[filename]
            info["status"]   = "done" if success else "failed"
            info["end_time"] = time.time()
            elapsed = info["end_time"] - (info["start_time"] or info["end_time"])
            info["speed"] = info["total"] / elapsed if elapsed > 0 else 0
            msg = f"[{'✓' if success else '✗'}] {filename}: {format_bytes(info['total'])} in {elapsed:.2f}s"
            self._log.append(msg)

    def get_progress(self, filename):
        with self._lock:
            return dict(self._progress.get(filename, {}))

    def all_progress(self):
        with self._lock:
            return {k: dict(v) for k, v in self._progress.items()}

    def log(self, message):
        with self._lock:
            ts = datetime.now().strftime("%H:%M:%S.%f")[:12]
            self._log.append(f"[{ts}] {message}")

    def get_log(self):
        with self._lock:
            return list(self._log)

    def overall_progress(self):
        with self._lock:
            if self._total_bytes == 0:
                return 0.0
            return min(1.0, self._done_bytes / self._total_bytes)


def format_bytes(b):
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


def format_speed(bps):
    return f"{format_bytes(bps)}/s"


# ── Simulated Download Worker ─────────────────────────────────────────────────
def download_worker(filename, total_bytes, manager, fail_prob=0.05):
    """Simulates downloading a file in random-sized chunks."""
    manager.start_file(filename)
    manager.log(f"Started: {filename} ({format_bytes(total_bytes)})")

    downloaded = 0
    chunk_size_range = (total_bytes // 20, total_bytes // 5)

    try:
        while downloaded < total_bytes:
            # Simulate network delay
            time.sleep(random.uniform(0.02, 0.12))

            # Random failure simulation
            if random.random() < fail_prob:
                raise ConnectionError(f"Network error on {filename}")

            chunk = random.randint(*chunk_size_range)
            chunk = min(chunk, total_bytes - downloaded)
            downloaded += chunk
            manager.update(filename, chunk)

        manager.finish_file(filename, success=True)
        manager.log(f"Completed: {filename}")

    except ConnectionError as e:
        manager.update(filename, 0, status="failed")
        manager.finish_file(filename, success=False)
        manager.log(f"FAILED: {filename} — {e}")


# ── Progress Display ──────────────────────────────────────────────────────────
def draw_progress_bar(downloaded, total, width=25):
    if total == 0:
        return "[" + "?" * width + "]"
    pct   = downloaded / total
    filled = int(pct * width)
    bar   = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct*100:>5.1f}%"


def display_all_progress(manager, files):
    all_p = manager.all_progress()
    overall = manager.overall_progress()

    print(f"\033[{len(files)+4}A", end="")  # move cursor up

    print(f"  {'─'*65}")
    print(f"  {'File':<28} {'Size':>8}  {'Progress':<35}  {'Status'}")
    print(f"  {'─'*65}")
    for filename in files:
        info = all_p.get(filename, {})
        dl   = info.get("downloaded", 0)
        tot  = info.get("total", 1)
        stat = info.get("status", "?")
        bar  = draw_progress_bar(dl, tot)
        status_icon = {"queued": "⏳", "downloading": "⬇", "done": "✓", "failed": "✗"}.get(stat, "?")
        print(f"  {filename:<28} {format_bytes(tot):>8}  {bar}  {status_icon} {stat}")

    ovr_bar = draw_progress_bar(int(overall * 100), 100)
    print(f"  {'─'*65}")
    print(f"  {'OVERALL':<28} {'':>8}  {ovr_bar}")


def run_downloads(file_list, max_workers=4, fail_prob=0.05):
    """
    file_list: list of (filename, size_bytes)
    Returns: manager after all downloads complete
    """
    manager = DownloadManager()
    for filename, size in file_list:
        manager.register(filename, size)

    semaphore = threading.Semaphore(max_workers)
    threads   = []

    def throttled_worker(filename, size):
        with semaphore:
            download_worker(filename, size, manager, fail_prob)

    # Print header area (reserve lines for live update)
    print("\n" * (len(file_list) + 4))

    # Start threads
    start_time = time.time()
    for filename, size in file_list:
        t = threading.Thread(
            target=throttled_worker,
            args=(filename, size),
            name=f"dl-{filename}",
            daemon=True,
        )
        threads.append(t)
        t.start()

    # Live progress display
    files = [f for f, _ in file_list]
    while any(t.is_alive() for t in threads):
        display_all_progress(manager, files)
        time.sleep(0.15)

    # Final display
    display_all_progress(manager, files)
    elapsed = time.time() - start_time

    return manager, elapsed


def sequential_estimate(file_list):
    """Estimate time if downloads were sequential (sum of individual times)."""
    total = sum(size for _, size in file_list)
    avg_speed = 500 * 1024   # 500 KB/s simulated
    return total / avg_speed


def print_summary(manager, elapsed, file_list, max_workers):
    log      = manager.get_log()
    all_p    = manager.all_progress()
    done     = sum(1 for v in all_p.values() if v["status"] == "done")
    failed   = sum(1 for v in all_p.values() if v["status"] == "failed")
    total_b  = sum(v["total"] for v in all_p.values())
    seq_time = sequential_estimate(file_list)

    print(f"\n  {'═'*60}")
    print(f"  DOWNLOAD SUMMARY")
    print(f"  {'─'*60}")
    print(f"  Files attempted  : {len(file_list)}")
    print(f"  Completed        : {done}")
    print(f"  Failed           : {failed}")
    print(f"  Total data       : {format_bytes(total_b)}")
    print(f"  Time taken       : {elapsed:.2f}s (with {max_workers} threads)")
    print(f"  Est. sequential  : {seq_time:.2f}s")
    print(f"  Speedup          : ~{seq_time/elapsed:.1f}×")
    print(f"\n  File Details:")
    print(f"  {'─'*55}")
    for filename, info in all_p.items():
        spd = format_speed(info.get("speed", 0))
        print(f"  {'✓' if info['status']=='done' else '✗'} {filename:<30} {spd:>12}")
    print(f"  {'═'*60}")
    print(f"\n  Event Log (last 10 entries):")
    for entry in log[-10:]:
        print(f"  {entry}")


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Multi-Threaded Downloader v1.0        ║")
    print("╚══════════════════════════════════════════╝")

    # Simulate a realistic file list
    files = [
        ("ubuntu-24.iso",         80 * 1024),
        ("python-3.12.tar.gz",    25 * 1024),
        ("dataset_v2.csv",        40 * 1024),
        ("library_docs.pdf",      12 * 1024),
        ("video_tutorial.mp4",    60 * 1024),
        ("model_weights.bin",     35 * 1024),
        ("config_backup.tar",     10 * 1024),
        ("source_code.zip",       20 * 1024),
    ]

    print(f"\n  Downloading {len(files)} files with max 4 concurrent workers...")
    print(f"  (Simulated downloads, fail probability: 5%)\n")

    manager, elapsed = run_downloads(files, max_workers=4, fail_prob=0.05)
    print_summary(manager, elapsed, files, max_workers=4)


if __name__ == "__main__":
    main()
