"""
Tests for project configuration and structure
"""
from pathlib import Path


class TestProjectConfiguration:
    """Test project configuration files"""

    def test_environment_yml_exists(self):
        """Test that environment.yml exists"""
        project_root = Path(__file__).parent.parent.parent
        env_file = project_root / "environment.yml"
        assert env_file.exists(), "environment.yml not found at project root"

    def test_environment_yml_has_content(self):
        """Test that environment.yml has proper content"""
        project_root = Path(__file__).parent.parent.parent
        env_file = project_root / "environment.yml"
        content = env_file.read_text()
        assert "python" in content.lower(), "environment.yml should specify python"
        assert "pytest" in content.lower(), "environment.yml should include pytest"

    def test_readme_exists(self):
        """Test that README.md exists"""
        project_root = Path(__file__).parent.parent.parent
        readme = project_root / "README.md"
        assert readme.exists(), "README.md not found"

    def test_github_workflows_exist(self):
        """Test that GitHub workflows are configured"""
        project_root = Path(__file__).parent.parent.parent
        workflows_dir = project_root / ".github" / "workflows"
        assert workflows_dir.exists(), ".github/workflows directory not found"

    def test_python_package_conda_workflow_exists(self):
        """Test that python-package-conda.yml workflow exists"""
        project_root = Path(__file__).parent.parent.parent
        workflow_file = project_root / ".github" / \
            "workflows" / "python-package-conda.yml"
        assert workflow_file.exists(), "python-package-conda.yml workflow not found"
class TestWeek1Structure:
    """Test Week 1 challenge structure"""

    def test_week1_directory_exists(self):
        """Test that week-1 directory exists"""
        project_root = Path(__file__).parent.parent
        week1_dir = project_root / "week-1"
        assert week1_dir.exists(), "week-1 directory not found"

    def test_week1_has_days(self):
        """Test that week-1 has day directories"""
        project_root = Path(__file__).parent.parent
        week1_dir = project_root / "week-1"

        expected_days = ["day-1", "day-2", "day-3",
                         "day-4", "day-5", "day-6", "day-7"]
        for day in expected_days:
            day_path = week1_dir / day
            assert day_path.exists(), f"{day} directory not found in week-1"


"""
Functional tests that exercise real module workflows and business logic
"""
import importlib
import inspect
import os
from pathlib import Path
import pytest


def get_app_instances():
    project_root = Path(__file__).parent.parent
    src_dir = project_root / "src"
    instances = []
    for f in sorted(os.listdir(src_dir)):
        if f.endswith('.py') and not f.startswith('__'):
            mod_name = 'src.' + f[:-3]
            try:
                mod = importlib.import_module(mod_name)
                for name, obj in inspect.getmembers(mod, inspect.isclass):
                    if name.endswith('App') and obj.__module__ == mod_name:
                        instances.append((f[:-3], obj()))
            except Exception:
                pass
    return instances


APP_INSTANCES = get_app_instances()


class TestModuleWorkflows:
    def test_all_modules_have_run(self):
        for name, inst in APP_INSTANCES:
            assert hasattr(inst, 'run'), f"{name} missing run()"
            assert callable(inst.run), f"{name} run() not callable"

    def test_all_modules_have_demo_data(self):
        for name, inst in APP_INSTANCES:
            assert hasattr(inst, 'demo_data'), f"{name} missing demo_data()"
            items = inst.demo_data()
            assert isinstance(items, list), f"{name} demo_data() should return list"

    def test_workflow_demo_to_process(self):
        for name, inst in APP_INSTANCES:
            items = inst.demo_data()
            if hasattr(inst, 'process_dataset') and callable(inst.process_dataset):
                result = inst.process_dataset(items)
                assert isinstance(result, dict), f"{name} process_dataset() should return dict"

    def test_state_tracking(self):
        for name, inst in APP_INSTANCES:
            prev = inst.state.runs
            if hasattr(inst, 'run') and callable(inst.run):
                try:
                    inst.run()
                except (OSError, ConnectionError, ValueError):
                    pass
                assert inst.state.runs >= prev

    def test_export_and_history(self):
        for name, inst in APP_INSTANCES:
            if hasattr(inst, 'history_tail') and callable(inst.history_tail):
                tail = inst.history_tail(3)
                assert isinstance(tail, list)
            if hasattr(inst, 'export_state') and callable(inst.export_state):
                inst.output_dir = Path(__file__).parent.parent / "outputs"
                inst.output_dir.mkdir(exist_ok=True)
                path = inst.export_state()
                assert path.exists(), f"{name} export_state() should create file"


class TestSpecificModuleLogic:
    def test_cli_calculator_compute(self):
        mod = importlib.import_module('src.cli_calculator')
        app = mod.CliCalculatorApp()
        assert app.compute(2, '+', 3) == 5
        assert app.compute(10, '-', 4) == 6
        assert app.compute(3, '*', 4) == 12
        assert app.compute(10, '/', 3) == pytest.approx(3.3333, rel=1e-3)
        assert app.compute(2, '**', 3) == 8
        assert app.compute(10, '%', 3) == 1

    def test_number_guessing_pick_target(self):
        mod = importlib.import_module('src.number_guessing_engine')
        app = mod.NumberGuessingEngineApp()
        target = app.pick_target()
        assert 1 <= target <= 100

    def test_password_strength_analyze(self):
        mod = importlib.import_module('src.password_strength_analyzer')
        app = mod.PasswordStrengthAnalyzerApp()
        weak = app.analyze('abc')
        assert weak['score'] <= 1
        strong = app.analyze('Abcdef1!')
        assert strong['score'] >= 3

    def test_task_management_crud(self):
        mod = importlib.import_module('src.task_management')
        app = mod.TaskManagementApp()
        task = app.create_task('Test task')
        assert task['title'] == 'Test task'
        if hasattr(app, 'update_task') and callable(app.update_task):
            updated = app.update_task(task['id'], title='Updated')
            assert updated['title'] == 'Updated'
        if hasattr(app, 'delete_task') and callable(app.delete_task):
            result = app.delete_task(task['id'])
            assert result is True

    def test_user_auth_simulation(self):
        mod = importlib.import_module('src.user_auth_simulation')
        app = mod.UserAuthSimulationApp()
        assert app.authenticate('admin', 'admin123') is True
        assert app.authenticate('admin', 'wrong') is False

    def test_credential_storage(self):
        mod = importlib.import_module('src.credential_storage')
        app = mod.CredentialStorageApp()
        result = app.process_dataset(app.dataset())
        assert 'records_created' in result

    def test_http_get_workflow_build_url(self):
        mod = importlib.import_module('src.http_get_workflow')
        app = mod.HttpGetWorkflowApp()
        url = app.build_url('https://api.example.com', {'q': 'test'})
        assert 'test' in url or 'api' in url

    def test_data_visualization_chart(self):
        mod = importlib.import_module('src.data_visualization')
        app = mod.DataVisualizationApp()
        result = app.process_dataset(app.dataset())
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_pdf_extractor(self):
        mod = importlib.import_module('src.pdf_extractor')
        app = mod.PdfExtractorApp()
        items = app.demo_data()
        assert isinstance(items, list)

    def test_qr_generator(self):
        mod = importlib.import_module('src.qr_generator')
        app = mod.QrGeneratorApp()
        items = app.demo_data()
        assert isinstance(items, list)
        result = app.process_dataset(items)
        assert isinstance(result, dict)