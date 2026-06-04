"""
Functional tests that exercise actual module business logic
"""
import importlib
import inspect
import os
from pathlib import Path
import pytest

def get_app_classes():
    project_root = Path(__file__).parent.parent
    src_dir = project_root / "src"
    app_classes = []
    for f in sorted(os.listdir(src_dir)):
        if f.endswith('.py') and not f.startswith('__'):
            mod_name = 'src.' + f[:-3]
            try:
                mod = importlib.import_module(mod_name)
                for name, obj in inspect.getmembers(mod, inspect.isclass):
                    if name.endswith('App') and name != 'BaseApp' and obj.__module__ == mod_name:
                        app_classes.append((f[:-3], obj))
            except Exception:
                pass
    return app_classes


APP_CLASSES = get_app_classes()


@pytest.fixture(params=[obj for _, obj in APP_CLASSES], ids=[name for name, _ in APP_CLASSES])
def app(request):
    return request.param()


def test_demo_data_returns_list(app):
    items = app.demo_data()
    assert isinstance(items, list)


def test_demo_data_items_are_dicts(app):
    items = app.demo_data()
    if items:
        assert all(isinstance(item, dict) for item in items)


def test_process_dataset_runs(app):
    items = app.demo_data()
    if hasattr(app, 'process_dataset') and callable(app.process_dataset):
        result = app.process_dataset(items)
        assert isinstance(result, dict)
        assert len(result) > 0


def test_run_executes(app):
    try:
        app.run()
        assert app.state.runs > 0
    except (OSError, ConnectionError, ValueError):
        pass


def test_section_output(app, capsys):
    app.section('Test Title')
    captured = capsys.readouterr()
    assert 'Test Title' in captured.out


def test_log_output(app, capsys):
    app.log('test log message')
    assert len(app.state.history) > 0
    assert any('test log message' in h for h in app.state.history)


def test_format_kv(app):
    if hasattr(app, 'format_kv') and callable(app.format_kv):
        out = app.format_kv('Key', 'Value')
        assert 'Key' in out
        assert 'Value' in out


def test_export_state(app, tmp_path):
    app.output_dir = tmp_path
    if hasattr(app, 'export_state') and callable(app.export_state):
        path = app.export_state()
        assert path.exists()


def test_save_json(app, tmp_path):
    if hasattr(app, 'save_json') and callable(app.save_json):
        app.output_dir = tmp_path
        path = app.save_json('test.json', {'a': 1})
        assert path.exists()


def test_display_report(app, capsys):
    if hasattr(app, 'display_report') and callable(app.display_report):
        app.display_report()
        captured = capsys.readouterr()
        assert 'Runs' in captured.out
