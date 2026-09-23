"""AST guard for the published package dependency direction."""

import ast
from pathlib import Path
import subprocess
import sys
import tomllib

import cedarkit.plots


PACKAGE_DIR = Path(cedarkit.plots.__file__).parent
FORBIDDEN = ("cedar_graph", "cemc_plots_kit")


def test_plots_does_not_import_upper_runtime_packages():
    offenders = []
    for path in PACKAGE_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module or ""]
            else:
                continue
            for name in names:
                for target in FORBIDDEN:
                    if name == target or name.startswith(f"{target}."):
                        offenders.append(f"{path.relative_to(PACKAGE_DIR)}:{node.lineno} imports {target}")
    assert not offenders, (
        "cedarkit-plots must not import cedar-graph or cemc-plots-kit; "
        "workflow-only imports are checked separately:\n"
        + "\n".join(offenders)
    )


def test_removed_workflow_implementations_do_not_return():
    for name in ("engine", "plan", "recipe"):
        assert not list((PACKAGE_DIR / name).rglob("*.py")), name
    assert not (PACKAGE_DIR / "style" / "units.py").exists()


def test_core_import_does_not_load_workflow_or_business_packages():
    script = """
import importlib.abc
import sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'reki' or fullname.startswith('reki.') or fullname.startswith(
                ('cedarkit.comp', 'cedarkit.plots.workflow', 'cedar_graph', 'cemc_plots_kit')):
            raise AssertionError(f'core attempted to import {fullname}')
sys.meta_path.insert(0, Guard())
from cedarkit.plots import Panel, Chart
assert Panel and Chart
assert not any(name == 'reki' or name.startswith(('reki.', 'cedarkit.comp',
    'cedarkit.plots.workflow', 'cedar_graph', 'cemc_plots_kit')) for name in sys.modules)
"""
    process = subprocess.run([sys.executable, "-I", "-c", script], capture_output=True, text=True)
    assert process.returncode == 0, process.stderr


def test_workflow_dependencies_are_optional():
    config = tomllib.loads((PACKAGE_DIR.parents[2] / "pyproject.toml").read_text(encoding="utf-8"))
    base = config["project"]["dependencies"]
    workflow = config["project"]["optional-dependencies"]["workflow"]
    assert not any(item.startswith(("reki", "cedarkit-comp")) for item in base)
    assert any(item.startswith("reki") for item in workflow)
    assert any(item.startswith("cedarkit-comp") for item in workflow)
