"""Recipe validate/migrate command line interface."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from .recipe import RecipeLoadError, dump_recipe, load_recipe


def _diagnostic(exc: Exception, as_json: bool) -> None:
    value = {"ok": False, "error": str(exc)} if as_json else str(exc)
    print(json.dumps(value, sort_keys=True) if as_json else value, file=sys.stderr)


def _validate(args: argparse.Namespace) -> int:
    try:
        loaded = load_recipe(sys.stdin.read() if args.path == "-" else args.path, origin="<stdin>" if args.path == "-" else None)
    except RecipeLoadError as exc:
        _diagnostic(exc, args.json)
        return 2
    value = {"ok": True, "version": loaded.source_version, "issues": [issue.__dict__ for issue in loaded.issues]}
    print(json.dumps(value, sort_keys=True) if args.json else "valid")
    return 0


def _migrate(args: argparse.Namespace) -> int:
    try:
        text = sys.stdin.read() if args.path == "-" else Path(args.path).read_text(encoding="utf-8")
        loaded = load_recipe(text, origin="<stdin>" if args.path == "-" else args.path, name=args.name)
    except (OSError, RecipeLoadError) as exc:
        _diagnostic(exc, args.json)
        return 2
    rendered = dump_recipe(loaded.recipe)
    status = 1 if loaded.source_version == 1 or loaded.issues else 0
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
                output.write(rendered)
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    elif args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cedarkit-plots recipe")
    # Keep the public two-word spelling while also accepting direct module use.
    if argv is None:
        argv = sys.argv[1:]
    if argv[:1] == ["recipe"]:
        argv = argv[1:]
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "migrate"):
        item = commands.add_parser(command)
        item.add_argument("path")
        item.add_argument("--json", action="store_true")
        if command == "migrate":
            item.add_argument("--name")
            item.add_argument("--check", action="store_true")
            item.add_argument("--output")
            item.add_argument("--in-place", action="store_true")
            item.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    return _validate(args) if args.command == "validate" else _migrate(args)


if __name__ == "__main__":
    raise SystemExit(main())
