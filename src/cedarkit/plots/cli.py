"""Validation and static plan preview for v3 workflow recipes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable


def _diagnostic(exc: Exception, as_json: bool) -> None:
    value = {"ok": False, "error": str(exc)} if as_json else str(exc)
    print(json.dumps(value, sort_keys=True) if as_json else value, file=sys.stderr)


def _paths(path: str) -> Iterable[Path | None]:
    """Yield one YAML document, or all YAML documents below a directory."""
    if path == "-":
        yield None
        return
    target = Path(path)
    if target.is_dir():
        yield from sorted(item for item in target.rglob("*")
                          if item.is_file() and item.suffix.lower() in {".yaml", ".yml"})
        return
    yield target


def _load(path: Path | None):
    from .workflow.recipe import load_recipe
    return load_recipe(sys.stdin.read() if path is None else path,
                       origin="<stdin>" if path is None else None)


def _validate(args: argparse.Namespace) -> int:
    from .workflow.recipe import RecipeLoadError

    values, failed = [], False
    for path in _paths(args.path):
        try:
            loaded = _load(path)
        except (RecipeLoadError, OSError) as exc:
            _diagnostic(exc, args.json)
            failed = True
            continue
        values.append({"path": loaded.origin, "ok": True,
                       "version": loaded.recipe.api_version, "name": loaded.recipe.metadata.name})
    if args.json:
        print(json.dumps(values, sort_keys=True))
    elif not failed:
        print(f"valid ({len(values)} recipe(s))")
    return 2 if failed else 0


def _plan(args: argparse.Namespace) -> int:
    from .plugins import PluginDiscoveryError
    from .workflow.discovery import discover_workflow
    from .workflow.plan import CompileContext, RecipeCompileError, compile_recipe
    from .workflow.recipe import RecipeLoadError

    paths = tuple(_paths(args.path))
    if len(paths) != 1:
        _diagnostic(RecipeLoadError("plan requires exactly one recipe file"), args.json)
        return 2
    params: dict[str, str] = {}
    for item in args.param:
        key, separator, value = item.partition("=")
        if not separator or not key:
            _diagnostic(RecipeLoadError("--param must use NAME=VALUE"), args.json)
            return 2
        params[key] = value
    try:
        loaded = _load(paths[0])
        registry = discover_workflow().ops
        plan = compile_recipe(loaded, CompileContext(start_time=args.start_time,
                              forecast_time=args.forecast_time, params=params), registry=registry)
    except (RecipeLoadError, RecipeCompileError, PluginDiscoveryError, OSError, TypeError, ValueError) as exc:
        _diagnostic(exc, args.json)
        return 2
    print(plan.to_json() if args.format == "json" else plan.summary())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cedarkit-plots recipe")
    if argv is None:
        argv = sys.argv[1:]
    if argv[:1] == ["recipe"]:
        argv = argv[1:]
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "plan"):
        item = commands.add_parser(command)
        item.add_argument("path")
        item.add_argument("--json", action="store_true")
        if command == "plan":
            item.add_argument("--start-time")
            item.add_argument("--forecast-time")
            item.add_argument("--param", action="append", default=[], metavar="NAME=VALUE")
            item.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args(argv)
    return _validate(args) if args.command == "validate" else _plan(args)


if __name__ == "__main__":
    raise SystemExit(main())
