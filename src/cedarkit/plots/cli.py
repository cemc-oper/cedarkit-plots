"""Recipe validation, migration, and static plan-preview command line interface."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Iterable

from .ops import OpRegistry
from .plan import CompileContext, RecipeCompileError, compile_recipe
from .plugins import discover
from .recipe import RecipeLoadError, dump_recipe, load_recipe


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
        yield from sorted(item for item in target.rglob("*.yaml") if item.is_file())
        return
    yield target


def _load(path: Path | None):
    return load_recipe(sys.stdin.read() if path is None else path,
                       origin="<stdin>" if path is None else None)


def _validate(args: argparse.Namespace) -> int:
    values, failed = [], False
    for path in _paths(args.path):
        try:
            loaded = _load(path)
        except RecipeLoadError as exc:
            _diagnostic(exc, args.json)
            failed = True
            continue
        values.append({"path": "<stdin>" if path is None else str(path), "ok": True,
                       "version": loaded.source_version,
                       "issues": [issue.__dict__ for issue in loaded.issues]})
    if args.json:
        print(json.dumps(values, sort_keys=True))
    elif not failed:
        print(f"valid ({len(values)} recipe(s))")
    return 2 if failed else 0


def _migrate(args: argparse.Namespace) -> int:
    paths = tuple(_paths(args.path))
    if len(paths) != 1 and (args.in_place or args.output):
        _diagnostic(RecipeLoadError("directory migration only supports --check or stdout"), args.json)
        return 2
    rendered_documents, status = [], 0
    for path in paths:
        try:
            text = sys.stdin.read() if path is None else path.read_text(encoding="utf-8")
            loaded = load_recipe(text, origin="<stdin>" if path is None else str(path), name=args.name)
        except (OSError, RecipeLoadError) as exc:
            _diagnostic(exc, args.json)
            return 2
        rendered_documents.append(dump_recipe(loaded.recipe))
        status = max(status, int(loaded.source_version == 1 or bool(loaded.issues)))
    if args.check:
        return status
    if args.in_place:
        if args.path == "-" or not args.force:
            _diagnostic(RecipeLoadError("--in-place requires a file and --force"), args.json)
            return 2
        target = Path(args.path)
        fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                output.write(rendered_documents[0])
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    elif args.output:
        Path(args.output).write_text(rendered_documents[0], encoding="utf-8")
    else:
        sys.stdout.write("".join(rendered_documents))
    return status


def _registry_with_plugins() -> OpRegistry:
    registry = OpRegistry.builtins()
    for provider, provenance in discover("cedarkit.plots.ops").providers:
        for descriptor in provider():
            registry.register_descriptor(descriptor, provenance=provenance)
    return registry


def _plan(args: argparse.Namespace) -> int:
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
        plan = compile_recipe(_load(paths[0]), CompileContext(start_time=args.start_time,
                              forecast_time=args.forecast_time, params=params),
                              registry=_registry_with_plugins())
    except (RecipeLoadError, RecipeCompileError, ValueError) as exc:
        _diagnostic(exc, args.json)
        return 2
    if args.format == "json":
        print(plan.to_json())
    else:
        print(plan.summary())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cedarkit-plots recipe")
    # Keep the public two-word spelling while also accepting direct module use.
    if argv is None:
        argv = sys.argv[1:]
    if argv[:1] == ["recipe"]:
        argv = argv[1:]
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "migrate", "plan"):
        item = commands.add_parser(command)
        item.add_argument("path")
        item.add_argument("--json", action="store_true")
        if command == "migrate":
            item.add_argument("--name")
            item.add_argument("--check", action="store_true")
            item.add_argument("--output")
            item.add_argument("--in-place", action="store_true")
            item.add_argument("--force", action="store_true")
        if command == "plan":
            item.add_argument("--start-time")
            item.add_argument("--forecast-time")
            item.add_argument("--param", action="append", default=[], metavar="NAME=VALUE")
            item.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args(argv)
    if args.command == "validate":
        return _validate(args)
    if args.command == "migrate":
        return _migrate(args)
    return _plan(args)


if __name__ == "__main__":
    raise SystemExit(main())
