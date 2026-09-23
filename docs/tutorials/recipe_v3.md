---
mystnb:
  execution_mode: 'off'
---

# Recipe v3 validation and planning

Install the workflow dependencies for recipe planning and execution:

```bash
pip install 'cedarkit-plots[workflow]'
```

For this source checkout, use `uv sync --extra workflow --extra test` before running the examples or tests. A basic `Panel`/`Chart` import and direct plotting need only the base package; the workflow extra supplies `reki` for parameter resolution and `cedarkit-comp` for scientific operations. Application packages such as cedar-graph and cemc-plots-kit remain separate.

The recipe CLI accepts only `cedarkit.plots/v3`. It does not migrate v1 or v2 documents. A minimal recipe is:

```yaml
api_version: cedarkit.plots/v3
kind: PlotRecipe
metadata: {name: example.t2m}
spec:
  data:
    temperature:
      field: {parameter: cedarkit.t2m}
      units: degC
      temperature_kind: absolute
  content:
    charts:
      - id: main
        plots:
          - {id: temperature, method: contourf, field: temperature, style: cemc.t2m:cn_summer}
```

`spec.data` declares fields, transforms and compute operations. `spec.content` declares stable Chart/Plot IDs, methods, styles, titles and colorbars. `spec.display` may select a `PanelTemplate` and provide layout or subplot settings. Loading validates the schema and references without fetching fields or constructing a Figure.

## Validate and inspect a plan

```bash
cedarkit-plots recipe validate recipe.yaml
cedarkit-plots recipe validate path/to/recipes --json
cedarkit-plots recipe validate - --json < recipe.yaml
cedarkit-plots recipe plan recipe.yaml --forecast-time 24h
cedarkit-plots recipe plan recipe.yaml --forecast-time 24h --format json
```

`validate` accepts a file, stdin, or a directory containing `.yaml` and `.yml` files. `plan` requires one recipe and accepts `--start-time`, `--forecast-time` and repeated `--param NAME=VALUE` arguments. It uses the same v3 loader, compiler and op plugin discovery as the Python workflow. Planning resolves parameter metadata and operation signatures but does not fetch field values or render a plot.

The JSON preview has `plan_schema_version: 3`, recipe/compiler/descriptor identities, context, ordered nodes, output bindings and slots, content/display declarations, issues and read batches. It contains no provider, callable or credentials. The default summary gives the recipe identity and node/read/issue counts.

The v3 loader, compiler, executor and renderer are available under `cedarkit.plots.workflow`. The workspace architecture document contains a runnable temperature example in its `d13/` directory.

## Plugins

The workflow uses the existing `cedarkit.plots.ops`, `cedarkit.plots.domains` and `cedarkit.plots.recipes` entry point groups. Op providers return `OpDescriptor` values; domain providers return `DomainDescriptor` values that create new `PanelTemplate` presets; recipe providers return an `importlib.resources` Traversable root. Discovery sorts providers deterministically and reports duplicate IDs with both registration sources. The CLI's plan command uses the discovered op registry.
