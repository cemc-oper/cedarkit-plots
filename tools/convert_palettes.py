"""Offline, reproducible palette conversion from audited source snapshots.

Run with --check to compare generated files without writing. Optional
--source-dir verifies original NCL/CSV bytes as well as the checked-in snapshot.
No network or business-plugin imports are performed.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re

import matplotlib.colors as mcolors
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RESOURCE = ROOT / "src/cedarkit/plots/resources/palettes"
TOOLS = ROOT / "tools"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def hex_color(rgb):
    if len(rgb) == 3:
        rgb = [*rgb, 255]
    return "#" + "".join(f"{channel:02x}" for channel in rgb)


def convert(source_dir=None):
    sources = json.loads((TOOLS / "palette_sources.json").read_text())["sources"]
    recipes = json.loads((TOOLS / "palette_recipes.json").read_text())
    for name, source in sources.items():
        colors = source["colors"]
        if digest(json.dumps(colors, separators=(",", ":")).encode()) != source["rgb_sha256"]:
            raise ValueError(f"snapshot checksum mismatch: {name}")
        rows = colors.values() if isinstance(colors, dict) else colors
        if any(len(row) != 3 or any(type(c) is not int or not 0 <= c <= 255 for c in row) for row in rows):
            raise ValueError(f"invalid RGB source values: {name}")
    palettes, old_palettes, audit, style_map = {}, {}, {}, {}
    named = {name: hex_color(rgb) for name, rgb in sources["named_colors"]["colors"].items()}
    named["transparent"] = "#ffffff00"
    old_named = {**named, "transparent": "#ffffffff"}
    if source_dir is not None:
        for key, source in sources.items():
            if "local_file" not in source:
                continue
            path = source_dir / source["local_file"]
            if digest(path.read_bytes()) != source["local_sha256"]:
                raise ValueError(f"source bytes changed: {path}")
            if key == "named_colors":
                rows = csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines())
                for row in rows:
                    name = row["name"].strip().lower()
                    if name in named and hex_color([int(row[k]) for k in ("R", "G", "B")]) != named[name]:
                        raise ValueError(f"named color mismatch: {name}")
            else:
                colors = [list(map(int, row)) for row in re.findall(
                    r"^[ \t]*(\d+)[ \t]+(\d+)[ \t]+(\d+)[ \t]*$", path.read_text(), re.M)]
                if colors != source["colors"]:
                    raise ValueError(f"source rows changed: {path}")

    def add(name, colors, old_colors, origins, derivation):
        if not colors or len(colors) != len(old_colors):
            raise ValueError(f"invalid conversion: {name}")
        entry = dict(colors=colors, under=colors[0], over=colors[-1], bad="#00000000",
                     interpolation="listed", sources=sorted(set(origins)), derivation=derivation)
        palettes[name], old_palettes[name] = entry, old_colors
        audit[name] = dict(count=len(colors), derivation=derivation, rows=[
            dict(index=i, old_rgba=old, new_rgba=new,
                 change="transparent alpha: 1 -> 0" if old != new else None)
            for i, (old, new) in enumerate(zip(old_colors, colors))])
        for old, new in zip(old_colors, colors):
            if old != new and (old, new) != ("#ffffffff", "#ffffff00"):
                raise ValueError(f"unexpected color change in {name}: {old} -> {new}")

    for name, source in sources.items():
        if source["status"] != "verified":
            continue
        colors = source["colors"]
        if digest(json.dumps(colors, separators=(",", ":")).encode()) != source["rgb_sha256"]:
            raise ValueError(f"snapshot checksum mismatch: {name}")
        colors = [hex_color(c) for c in colors]
        prefix = "cemc" if name.startswith("cn_") else "source"
        add(f"{prefix}.{name}", colors, colors, [name], {"source": name})

    def select(source, indices):
        # Freeze the legacy ListedColormap under/over lookup, not Python's
        # negative-index semantics. Every out-of-range request is recorded.
        n = len(palettes[source]["colors"])
        actual = [min(max(int(i), 0), n - 1) for i in indices]
        return ([palettes[source]["colors"][i] for i in actual],
                [old_palettes[source][i] for i in actual], actual)

    indices = [i - 2 for i in [175, 160, 156, 140, 125, 110, 100, 90, 80, 60]]
    colors, old, actual = select("source.BkBlAqGrYeOrReViWh200", indices)
    add("cemc.cn_pte", colors + ["#ffffffff"], old + ["#ffffffff"],
        ["BkBlAqGrYeOrReViWh200"], {"source": "source.BkBlAqGrYeOrReViWh200", "indices": indices, "append": ["#ffffffff"]})
    colors = palettes["source.testcmap"]["colors"] + ["#ff00ffff", "#4d4d4dff"]
    add("cemc.cn_tdew", colors, colors, ["testcmap"], {"source": "source.testcmap", "append": ["#ff00ffff", "#4d4d4dff"]})
    extra = [named[n.lower()] for n in recipes["shr_names"]]
    colors = palettes["source.WhViBlGrYeOrRe"]["colors"] + extra
    add("cemc.cn_shr", colors, colors, ["WhViBlGrYeOrRe", "named_colors"],
        {"source": "source.WhViBlGrYeOrRe", "append_names": recipes["shr_names"]})

    for name, style in recipes["styles"].items():
        cmap = style["colormap"]
        source = None
        if "ncl" in cmap or "rgb_table" in cmap:
            source = "source." + cmap["ncl"] if "ncl" in cmap else "cemc." + cmap["rgb_table"]
            n = len(palettes[source]["colors"])
            if "count" in cmap:
                indices = np.rint(np.linspace(cmap.get("spread_start", 0), cmap.get("spread_end", n - 1), cmap["count"])).astype(int).tolist()
            elif "index" in cmap:
                indices = cmap["index"] if isinstance(cmap["index"], list) else [cmap["index"]]
                indices = [i + cmap.get("index_offset", 0) for i in indices]
            else:
                indices = list(range(n))
            colors, old, actual = select(source, indices)
            origins = palettes[source]["sources"]
            derivation = {"source": source, "requested_indices": indices, "resolved_indices": actual, "legacy_spec": cmap}
        elif "ncl_colors" in cmap:
            colors = [named[n.lower()] for n in cmap["ncl_colors"]]
            old = [old_named[n.lower()] for n in cmap["ncl_colors"]]
            origins, derivation = ["named_colors"], {"names": cmap["ncl_colors"]}
        else:
            colors = [mcolors.to_hex(c, keep_alpha=True) for c in cmap["colors"]]
            old, origins, derivation = colors, [], {"explicit": cmap["colors"]}
        add(name, colors, old, origins, derivation)
        migration = {"palette": name, "levels": style.get("levels"), "special_colors": {k: palettes[name][k] for k in ("under", "over", "bad")}}
        if source is not None:
            label = style.get("label", {})
            if "color_index" in label:
                idx = label["color_index"]
                migration["label_rgba"] = select(source, idx if isinstance(idx, list) else [idx])[0]
            highlights = style.get("highlight", [])
            if isinstance(highlights, dict):
                highlights = [highlights]
            migration["highlights"] = []
            for highlight in highlights:
                item = dict(highlight)
                if "color_index" in item:
                    item["color"] = select(source, [item.pop("color_index")])[0][0]
                migration["highlights"].append(item)
        style_map[name] = migration
    provenance = {name: {k: v for k, v in s.items() if k not in {"colors", "excluded"}}
                  for name, s in sources.items() if s["status"] in {"verified", "verified_subset"}}
    catalog = {"schema_version": 1, "palettes": palettes, "named_colors": named, "provenance": provenance}
    return {RESOURCE / "catalog.json": dump(catalog), TOOLS / "palette_audit.json": dump(audit),
            TOOLS / "style_palette_map.json": dump(style_map)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--source-dir", type=Path)
    args = parser.parse_args()
    outputs = convert(args.source_dir)
    for path, text in outputs.items():
        if args.check:
            if path.read_text() != text:
                raise SystemExit(f"generated file is stale: {path}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
    print("Native palettes, per-color audit and style mapping verified")


if __name__ == "__main__":
    main()
