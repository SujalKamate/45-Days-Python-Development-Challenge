"""Automated state difference analysis and visual changelog generation for exported snapshots."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set
import datetime
import difflib
import json
import os
import uuid


class DiffEntry:
    """A single changed value between two state snapshots."""

    def __init__(self, path: str, change_type: str,
                 old_value: Any = None, new_value: Any = None,
                 severity: str = 'info') -> None:
        self.path = path
        self.change_type = change_type
        self.old_value = old_value
        self.new_value = new_value
        self.severity = severity

    def to_dict(self) -> Dict[str, Any]:
        return {
            'path': self.path,
            'change_type': self.change_type,
            'old_value': self._safe_repr(self.old_value),
            'new_value': self._safe_repr(self.new_value),
            'severity': self.severity,
        }

    @staticmethod
    def _safe_repr(val: Any) -> Any:
        if isinstance(val, (str, int, float, bool, type(None))):
            return val
        if isinstance(val, (list, tuple)):
            return [str(v)[:100] for v in val[:20]]
        if isinstance(val, dict):
            return {k: str(v)[:100] for k, v in list(val.items())[:20]}
        return str(val)[:200]


class DiffResult:
    """Collection of diff entries between two states."""

    ADDED = 'added'
    REMOVED = 'removed'
    MODIFIED = 'modified'
    UNCHANGED = 'unchanged'

    def __init__(self, before_label: str = 'before',
                 after_label: str = 'after') -> None:
        self.before_label = before_label
        self.after_label = after_label
        self.entries: List[DiffEntry] = []

    def add(self, entry: DiffEntry) -> None:
        self.entries.append(entry)

    def summary(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for e in self.entries:
            counts[e.change_type] = counts.get(e.change_type, 0) + 1
        return counts

    def filter_by_severity(self, min_severity: str = 'warning') -> DiffResult:
        order = {'info': 0, 'warning': 1, 'critical': 2}
        min_level = order.get(min_severity, 0)
        filtered = DiffResult(self.before_label, self.after_label)
        for e in self.entries:
            if order.get(e.severity, 0) >= min_level:
                filtered.add(e)
        return filtered

    def changes_by_type(self, change_type: str) -> List[DiffEntry]:
        return [e for e in self.entries if e.change_type == change_type]

    @property
    def has_changes(self) -> bool:
        return any(e.change_type != self.UNCHANGED for e in self.entries)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'before': self.before_label,
            'after': self.after_label,
            'summary': self.summary(),
            'changes': [e.to_dict() for e in self.entries],
        }


class ChangeFilter:
    """Filter insignificant or noisy changes from diff results."""

    def __init__(self) -> None:
        self._ignored_paths: Set[str] = set()
        self._ignored_types: Set[str] = set()
        self._max_value_chars = 500

    def ignore_path(self, path: str) -> None:
        self._ignored_paths.add(path)

    def ignore_type(self, type_name: str) -> None:
        self._ignored_types.add(type_name)

    def should_include(self, entry: DiffEntry) -> bool:
        if entry.path in self._ignored_paths:
            return False
        if entry.change_type in self._ignored_types:
            return False
        return True

    def apply(self, result: DiffResult) -> DiffResult:
        filtered = DiffResult(result.before_label, result.after_label)
        for e in result.entries:
            if self.should_include(e):
                filtered.add(e)
        return filtered


class StateDiffer:
    """Deep-compare two state dictionaries and produce a structured diff."""

    def diff(self, before: Dict[str, Any], after: Dict[str, Any],
             before_label: str = 'before',
             after_label: str = 'after') -> DiffResult:
        result = DiffResult(before_label, after_label)
        self._compare('', before, after, result)
        return result

    def _compare(self, prefix: str, before: Any, after: Any,
                 result: DiffResult) -> None:
        if isinstance(before, dict) and isinstance(after, dict):
            self._compare_dicts(prefix, before, after, result)
        elif isinstance(before, list) and isinstance(after, list):
            self._compare_lists(prefix, before, after, result)
        elif before != after:
            sev = self._severity(before, after)
            result.add(DiffEntry(prefix, DiffResult.MODIFIED, before, after, sev))

    def _compare_dicts(self, prefix: str, before: Dict[str, Any],
                       after: Dict[str, Any], result: DiffResult) -> None:
        all_keys = set(before.keys()) | set(after.keys())
        for k in sorted(all_keys):
            path = f'{prefix}.{k}' if prefix else k
            if k not in before:
                sev = self._severity(None, after[k])
                result.add(DiffEntry(path, DiffResult.ADDED, None, after[k], sev))
            elif k not in after:
                sev = self._severity(before[k], None)
                result.add(DiffEntry(path, DiffResult.REMOVED, before[k], None, sev))
            else:
                self._compare(path, before[k], after[k], result)

    def _compare_lists(self, prefix: str, before: List[Any],
                       after: List[Any], result: DiffResult) -> None:
        max_len = max(len(before), len(after))
        for i in range(max_len):
            path = f'{prefix}[{i}]'
            if i >= len(before):
                sev = self._severity(None, after[i])
                result.add(DiffEntry(path, DiffResult.ADDED, None, after[i], sev))
            elif i >= len(after):
                sev = self._severity(before[i], None)
                result.add(DiffEntry(path, DiffResult.REMOVED, before[i], None, sev))
            elif before[i] != after[i]:
                sev = self._severity(before[i], after[i])
                result.add(DiffEntry(path, DiffResult.MODIFIED, before[i], after[i], sev))

    @staticmethod
    def _severity(old: Any, new: Any) -> str:
        if old is None or new is None:
            return 'warning'
        if isinstance(old, (int, float)) and isinstance(new, (int, float)):
            if abs(old - new) > 0.5 * abs(old) if old != 0 else abs(new) > 0:
                return 'warning'
        if isinstance(old, str) and isinstance(new, str):
            if len(old) != len(new):
                return 'warning'
        return 'info'

    def diff_raw(self, before: Dict[str, Any], after: Dict[str, Any]) -> str:
        before_json = json.dumps(before, indent=2, default=str, sort_keys=True)
        after_json = json.dumps(after, indent=2, default=str, sort_keys=True)
        return '\n'.join(difflib.unified_diff(
            before_json.splitlines(),
            after_json.splitlines(),
            fromfile='before', tofile='after', lineterm='',
        ))


class ChangelogEntry:
    """A single entry in the changelog."""

    def __init__(self, version: str, timestamp: str,
                 changes: List[Dict[str, Any]],
                 summary: Dict[str, int]) -> None:
        self.version = version
        self.timestamp = timestamp
        self.changes = changes
        self.summary = summary

    def to_dict(self) -> Dict[str, Any]:
        return {
            'version': self.version,
            'timestamp': self.timestamp,
            'summary': self.summary,
            'changes': self.changes,
        }


class ChangelogGenerator:
    """Generate structured changelogs from diff results."""

    def __init__(self) -> None:
        self._entries: List[ChangelogEntry] = []

    def add_entry(self, version: str, diff: DiffResult) -> None:
        entry = ChangelogEntry(
            version=version,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            changes=[e.to_dict() for e in diff.entries if e.change_type != DiffResult.UNCHANGED],
            summary=diff.summary(),
        )
        self._entries.append(entry)

    def entries(self, limit: int = 100) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._entries[-limit:]]

    def last(self) -> Optional[Dict[str, Any]]:
        return self._entries[-1].to_dict() if self._entries else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_entries': len(self._entries),
            'entries': self.entries(9999),
        }


class VisualReportBuilder:
    """Build human-friendly changelog reports."""

    @staticmethod
    def text_report(changelog: ChangelogGenerator) -> str:
        lines = ['=== State Changelog ===', '']
        for entry in reversed(changelog._entries):
            lines.append(f'Version: {entry.version}')
            lines.append(f'Time: {entry.timestamp}')
            s = entry.summary
            parts = [f'{k}: {v}' for k, v in s.items() if v > 0]
            lines.append(f'Changes: {", ".join(parts) if parts else "none"}')
            if entry.changes:
                for ch in entry.changes[:20]:
                    lines.append(f'  [{ch["change_type"]}] {ch["path"]}')
            lines.append('')
        return '\n'.join(lines)

    @staticmethod
    def html_report(changelog: ChangelogGenerator) -> str:
        rows = []
        for entry in reversed(changelog._entries):
            s = entry.summary
            color = '#4caf50'
            if s.get('removed', 0) or s.get('modified', 0):
                color = '#ff9800'
            if s.get('critical', 0):
                color = '#f44336'
            rows.append(f'''<tr style="border-bottom:1px solid #ddd">
<td style="padding:8px">{entry.version}</td>
<td style="padding:8px">{entry.timestamp[:19]}</td>
<td style="padding:8px;color:{color}">{', '.join(f'{k}:{v}' for k,v in s.items() if v)}</td>
<td style="padding:8px"><pre style="font-size:11px;margin:0">{chr(10).join(f'[{c["change_type"]}] {c["path"]}' for c in entry.changes[:15])}</pre></td>
</tr>''')
        return f'''<!DOCTYPE html><html><head><meta charset="utf-8"><title>State Changelog</title></head>
<body style="font-family:sans-serif;margin:20px">
<h2>State Changelog</h2>
<table style="border-collapse:collapse;width:100%">
<tr style="background:#f5f5f5"><th style="padding:8px;text-align:left">Version</th><th style="padding:8px;text-align:left">Time</th><th style="padding:8px;text-align:left">Summary</th><th style="padding:8px;text-align:left">Changes</th></tr>
{''.join(rows)}
</table></body></html>'''

    @staticmethod
    def markdown_report(changelog: ChangelogGenerator) -> str:
        lines = ['# State Changelog', '']
        for entry in reversed(changelog._entries):
            s = entry.summary
            lines.append(f'## Version {entry.version}')
            lines.append(f'- **Time:** {entry.timestamp}')
            lines.append(f'- **Summary:** {", ".join(f"{k}:{v}" for k,v in s.items() if v)}')
            if entry.changes:
                lines.append('- Changes:')
                for c in entry.changes[:20]:
                    lines.append(f'  - `[{c["change_type"]}]` {c["path"]}')
            lines.append('')
        return '\n'.join(lines)


class StateDiffEngine:
    """Top-level state difference analysis and changelog engine."""

    def __init__(self) -> None:
        self._differ = StateDiffer()
        self._filter = ChangeFilter()
        self._changelog = ChangelogGenerator()
        self._snapshots: Dict[str, Dict[str, Any]] = {}

    @property
    def differ(self) -> StateDiffer:
        return self._differ

    @property
    def filter(self) -> ChangeFilter:
        return self._filter

    @property
    def changelog(self) -> ChangelogGenerator:
        return self._changelog

    def save_snapshot(self, key: str, state: Dict[str, Any]) -> None:
        self._snapshots[key] = dict(state)

    def get_snapshot(self, key: str) -> Optional[Dict[str, Any]]:
        return self._snapshots.get(key)

    def diff_snapshots(self, before_key: str, after_key: str,
                       filtered: bool = True) -> DiffResult:
        before = self._snapshots.get(before_key, {})
        after = self._snapshots.get(after_key, {})
        result = self._differ.diff(before, after, before_key, after_key)
        if filtered:
            result = self._filter.apply(result)
        return result

    def diff_states(self, before: Dict[str, Any], after: Dict[str, Any],
                    before_label: str = 'before', after_label: str = 'after',
                    filtered: bool = True) -> DiffResult:
        result = self._differ.diff(before, after, before_label, after_label)
        if filtered:
            result = self._filter.apply(result)
        return result

    def record_change(self, version: str, before: Dict[str, Any],
                      after: Dict[str, Any]) -> DiffResult:
        diff = self.diff_states(before, after, f'v{version}_before', f'v{version}_after')
        self._changelog.add_entry(version, diff)
        return diff

    def ignore_path(self, path: str) -> None:
        self._filter.ignore_path(path)

    def ignore_type(self, type_name: str) -> None:
        self._filter.ignore_type(type_name)

    def text_changelog(self) -> str:
        return VisualReportBuilder.text_report(self._changelog)

    def html_changelog(self) -> str:
        return VisualReportBuilder.html_report(self._changelog)

    def markdown_changelog(self) -> str:
        return VisualReportBuilder.markdown_report(self._changelog)

    def summary(self) -> Dict[str, Any]:
        return {
            'snapshots_stored': len(self._snapshots),
            'changelog_entries': len(self._changelog._entries),
            'ignored_paths': len(self._filter._ignored_paths),
            'ignored_types': len(self._filter._ignored_types),
        }

    def report_text(self) -> str:
        s = self.summary()
        return (
            f'State Diff Engine\n'
            f'  Snapshots: {s["snapshots_stored"]}\n'
            f'  Changelog entries: {s["changelog_entries"]}\n'
            f'  Ignored paths: {s["ignored_paths"]}'
        )

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        sp = os.path.join(dir, 'state_diff.json')
        with open(sp, 'w') as f:
            json.dump(self.summary(), f, indent=2)
        paths.append(sp)
        cp = os.path.join(dir, 'state_changelog.json')
        with open(cp, 'w') as f:
            json.dump(self._changelog.to_dict(), f, indent=2)
        paths.append(cp)
        hp = os.path.join(dir, 'state_changelog.html')
        with open(hp, 'w') as f:
            f.write(self.html_changelog())
        paths.append(hp)
        mp = os.path.join(dir, 'state_changelog.md')
        with open(mp, 'w') as f:
            f.write(self.markdown_changelog())
        paths.append(mp)
        return paths
