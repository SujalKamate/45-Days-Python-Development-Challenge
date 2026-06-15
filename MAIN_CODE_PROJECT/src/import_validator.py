"""Import-time static analysis and AST validation framework for code quality enforcement."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import ast
import datetime
import json
import os
import sys
import textwrap
import uuid


class ValidationFinding:
    """A single validation finding with severity, location, and message."""

    def __init__(self, rule: str, message: str, severity: str = 'warning',
                 lineno: int = 0, col_offset: int = 0,
                 filename: str = '') -> None:
        self.id = uuid.uuid4().hex[:8]
        self.rule = rule
        self.message = message
        self.severity = severity
        self.lineno = lineno
        self.col_offset = col_offset
        self.filename = filename

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'rule': self.rule,
            'message': self.message,
            'severity': self.severity,
            'lineno': self.lineno,
            'col_offset': self.col_offset,
            'filename': self.filename,
        }

    def __repr__(self) -> str:
        loc = f'{self.filename}:{self.lineno}' if self.filename else f'line {self.lineno}'
        return f'[{self.severity.upper()}] {self.rule}: {self.message} ({loc})'


class ValidationReport:
    """Collection of validation findings for a source file."""

    def __init__(self, filename: str = '') -> None:
        self.filename = filename
        self.findings: List[ValidationFinding] = []
        self.passed = True

    def add(self, finding: ValidationFinding) -> None:
        self.findings.append(finding)
        if finding.severity == 'error':
            self.passed = False

    def merge(self, other: ValidationReport) -> None:
        self.findings.extend(other.findings)
        if not other.passed:
            self.passed = False

    def summary(self) -> Dict[str, Any]:
        total = len(self.findings)
        errors = sum(1 for f in self.findings if f.severity == 'error')
        warnings = sum(1 for f in self.findings if f.severity == 'warning')
        infos = sum(1 for f in self.findings if f.severity == 'info')
        return {
            'filename': self.filename,
            'total': total,
            'errors': errors,
            'warnings': warnings,
            'infos': infos,
            'passed': self.passed,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            'filename': self.filename,
            'passed': self.passed,
            'findings': [f.to_dict() for f in self.findings],
            'summary': self.summary(),
        }


class ASTRule:
    """Base class for an AST validation rule."""

    def __init__(self, name: str, severity: str = 'warning') -> None:
        self.name = name
        self.severity = severity

    def check(self, tree: ast.AST, filename: str = '') -> ValidationReport:
        report = ValidationReport(filename)
        self._visit(tree, report, filename)
        return report

    def _visit(self, node: ast.AST, report: ValidationReport, filename: str) -> None:
        for child in ast.walk(node):
            self._check_node(child, report, filename)

    def _check_node(self, node: ast.AST, report: ValidationReport, filename: str) -> None:
        pass

    def _finding(self, message: str, lineno: int = 0,
                 col_offset: int = 0, filename: str = '') -> ValidationFinding:
        return ValidationFinding(self.name, message, self.severity, lineno, col_offset, filename)


class NoEvalRule(ASTRule):
    """Detect use of eval() and exec()."""

    def __init__(self, severity: str = 'error') -> None:
        super().__init__('no-eval', severity)

    def _check_node(self, node: ast.AST, report: ValidationReport, filename: str) -> None:
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in ('eval', 'exec'):
                report.add(self._finding(
                    f'Use of {node.func.id}() is forbidden',
                    node.lineno, node.col_offset, filename))


class NoImportStarRule(ASTRule):
    """Detect `from module import *`."""

    def __init__(self, severity: str = 'warning') -> None:
        super().__init__('no-import-star', severity)

    def _check_node(self, node: ast.AST, report: ValidationReport, filename: str) -> None:
        if isinstance(node, ast.ImportFrom) and node.names and node.names[0].name == '*':
            report.add(self._finding(
                'Wildcard imports are discouraged',
                node.lineno, node.col_offset, filename))


class NoMutableDefaultsRule(ASTRule):
    """Detect mutable default arguments in function definitions."""

    def __init__(self, severity: str = 'warning') -> None:
        super().__init__('no-mutable-defaults', severity)

    def _check_node(self, node: ast.AST, report: ValidationReport, filename: str) -> None:
        if isinstance(node, ast.FunctionDef):
            for default in node.args.defaults + node.args.kw_defaults:
                if default is not None and isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    report.add(self._finding(
                        'Mutable default argument detected',
                        node.lineno, default.col_offset, filename))


class MaxFunctionLinesRule(ASTRule):
    """Enforce maximum lines per function."""

    def __init__(self, max_lines: int = 40, severity: str = 'warning') -> None:
        super().__init__('max-function-lines', severity)
        self.max_lines = max_lines

    def _check_node(self, node: ast.AST, report: ValidationReport, filename: str) -> None:
        if isinstance(node, ast.FunctionDef):
            line_count = node.end_lineno - node.lineno if node.end_lineno else 0
            if line_count > self.max_lines:
                report.add(self._finding(
                    f'Function {node.name} has {line_count} lines (max {self.max_lines})',
                    node.lineno, 0, filename))


class MaxNestingDepthRule(ASTRule):
    """Detect excessive nesting depth."""

    def __init__(self, max_depth: int = 4, severity: str = 'warning') -> None:
        super().__init__('max-nesting-depth', severity)
        self.max_depth = max_depth

    def _visit(self, node: ast.AST, report: ValidationReport, filename: str) -> None:
        self._walk_depth(node, report, filename, 0)

    def _walk_depth(self, node: ast.AST, report: ValidationReport,
                    filename: str, depth: int) -> None:
        if isinstance(node, (ast.If, ast.For, ast.While, ast.Try, ast.With)):
            depth += 1
            if depth > self.max_depth:
                report.add(self._finding(
                    f'Nesting depth {depth} exceeds max {self.max_depth}',
                    node.lineno, 0, filename))
        for child in ast.iter_child_nodes(node):
            self._walk_depth(child, report, filename, depth)


class NamingConventionRule(ASTRule):
    """Enforce naming conventions: snake_case for functions/vars, PascalCase for classes."""

    def __init__(self, severity: str = 'warning') -> None:
        super().__init__('naming-convention', severity)

    def _check_node(self, node: ast.AST, report: ValidationReport, filename: str) -> None:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith('_'):
            if not self._is_snake_case(node.name):
                report.add(self._finding(
                    f'Function {node.name} should use snake_case', node.lineno, 0, filename))
        if isinstance(node, ast.ClassDef):
            if not self._is_pascal_case(node.name):
                report.add(self._finding(
                    f'Class {node.name} should use PascalCase', node.lineno, 0, filename))
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and not target.id.startswith('_'):
                    if not self._is_snake_case(target.id):
                        report.add(self._finding(
                            f'Variable {target.id} should use snake_case',
                            target.lineno, target.col_offset, filename))

    @staticmethod
    def _is_snake_case(name: str) -> bool:
        return all(c.islower() or c.isdigit() or c == '_' for c in name) and name.islower()

    @staticmethod
    def _is_pascal_case(name: str) -> bool:
        return bool(name) and name[0].isupper() and '_' not in name


class DocstringRule(ASTRule):
    """Require docstrings on modules, classes, and public functions."""

    def __init__(self, severity: str = 'info') -> None:
        super().__init__('missing-docstring', severity)

    def _check_node(self, node: ast.AST, report: ValidationReport, filename: str) -> None:
        if isinstance(node, ast.Module):
            if not ast.get_docstring(node):
                report.add(self._finding('Module missing docstring', 1, 0, filename))
        elif isinstance(node, ast.ClassDef):
            if not ast.get_docstring(node):
                report.add(self._finding(
                    f'Class {node.name} missing docstring', node.lineno, 0, filename))
        elif isinstance(node, ast.FunctionDef):
            if not node.name.startswith('_') and not ast.get_docstring(node):
                report.add(self._finding(
                    f'Function {node.name} missing docstring', node.lineno, 0, filename))


class ASTValidator:
    """Apply a set of rules to parsed ASTs."""

    def __init__(self, rules: Optional[List[ASTRule]] = None,
                 strict_mode: bool = False) -> None:
        self._rules = rules or self._default_rules()
        self.strict_mode = strict_mode

    @staticmethod
    def _default_rules() -> List[ASTRule]:
        return [
            NoEvalRule(),
            NoImportStarRule(),
            NoMutableDefaultsRule(),
            MaxFunctionLinesRule(),
            MaxNestingDepthRule(),
            NamingConventionRule(),
            DocstringRule(),
        ]

    def add_rule(self, rule: ASTRule) -> None:
        self._rules.append(rule)

    def remove_rule(self, name: str) -> bool:
        for i, r in enumerate(self._rules):
            if r.name == name:
                self._rules.pop(i)
                return True
        return False

    def list_rules(self) -> List[str]:
        return [r.name for r in self._rules]

    def validate_source(self, source: str, filename: str = '') -> ValidationReport:
        try:
            tree = ast.parse(source, filename=filename)
        except SyntaxError as e:
            report = ValidationReport(filename)
            report.add(ValidationFinding(
                'syntax-error', str(e), 'error', e.lineno or 0, e.offset or 0, filename))
            report.passed = False
            return report

        report = ValidationReport(filename)
        for rule in self._rules:
            try:
                rule_report = rule.check(tree, filename)
                report.merge(rule_report)
            except Exception as e:
                report.add(ValidationFinding(
                    'rule-error', f'Rule {rule.name} failed: {e}', 'error', 0, 0, filename))
        return report

    def validate_file(self, path: str) -> ValidationReport:
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                source = f.read()
        except IOError as e:
            report = ValidationReport(path)
            report.add(ValidationFinding('io-error', str(e), 'error', 0, 0, path))
            report.passed = False
            return report
        return self.validate_source(source, path)


class ImportValidator:
    """Import hook that validates source at import time."""

    def __init__(self, validator: ASTValidator) -> None:
        self._validator = validator
        self._history: List[Dict[str, Any]] = []

    def validate_module(self, module_name: str) -> ValidationReport:
        spec = __import__(module_name)
        filepath = getattr(spec, '__file__', '') if hasattr(spec, '__file__') else ''
        if filepath and filepath.endswith('.py'):
            report = self._validator.validate_file(filepath)
            if report.findings:
                self._history.append({
                    'module': module_name,
                    'file': filepath,
                    'passed': report.passed,
                    'findings': len(report.findings),
                    'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                })
            return report
        return ValidationReport(filepath)

    def history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._history[-limit:]


class ImportValidationEngine:
    """Top-level import-time static analysis and AST validation framework."""

    def __init__(self, strict_mode: bool = False) -> None:
        self._validator = ASTValidator(strict_mode=strict_mode)
        self._import_validator = ImportValidator(self._validator)

    @property
    def validator(self) -> ASTValidator:
        return self._validator

    def validate_source(self, source: str, filename: str = '') -> ValidationReport:
        return self._validator.validate_source(source, filename)

    def validate_file(self, path: str) -> ValidationReport:
        return self._validator.validate_file(path)

    def validate_module(self, module_name: str) -> ValidationReport:
        return self._import_validator.validate_module(module_name)

    def add_rule(self, rule: ASTRule) -> None:
        self._validator.add_rule(rule)

    def remove_rule(self, name: str) -> bool:
        return self._validator.remove_rule(name)

    def list_rules(self) -> List[str]:
        return self._validator.list_rules()

    def set_strict_mode(self, enabled: bool) -> None:
        self._validator.strict_mode = enabled

    def validation_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._import_validator.history(limit)

    def summary(self) -> Dict[str, Any]:
        history = self.validation_history(9999)
        total = len(history)
        passed = sum(1 for h in history if h['passed'])
        return {
            'rules_registered': len(self._validator.list_rules()),
            'strict_mode': self._validator.strict_mode,
            'validations_performed': total,
            'passed': passed,
            'failed': total - passed,
        }

    def report_text(self) -> str:
        s = self.summary()
        return (
            f'Import Validation Engine\n'
            f'  Rules: {s["rules_registered"]} ({", ".join(self._validator.list_rules())})\n'
            f'  Strict mode: {s["strict_mode"]}\n'
            f'  Validations: {s["validations_performed"]} ({s["passed"]} passed, {s["failed"]} failed)'
        )

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        sp = os.path.join(dir, 'import_validator.json')
        with open(sp, 'w') as f:
            json.dump(self.summary(), f, indent=2)
        paths.append(sp)
        hp = os.path.join(dir, 'import_validation_history.json')
        with open(hp, 'w') as f:
            json.dump(self.validation_history(limit=500), f, indent=2)
        paths.append(hp)
        return paths
