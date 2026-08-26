"""AST guard for the published package dependency direction."""

import ast
from pathlib import Path

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
        "cedarkit-plots may depend on reki but not cedar-graph or "
        "cemc-plots-kit; dependency direction is plots -> reki:\n"
        + "\n".join(offenders)
    )
