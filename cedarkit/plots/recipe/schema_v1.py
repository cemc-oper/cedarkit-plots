"""The frozen legacy recipe schema.

New features belong in :mod:`cedarkit.plots.recipe.schema_v2`; these aliases
exist solely so consumers can name the compatibility boundary explicitly.
"""

from ..engine.recipe import (ColorbarSpec, ComputeSpec, DataFieldSpec, DomainSpec,
                             LayerSpec, LevelSpec, ParamSpec, Recipe, TransformSpec)

RecipeV1 = Recipe

__all__ = ["RecipeV1", "Recipe", "ColorbarSpec", "ComputeSpec", "DataFieldSpec",
           "DomainSpec", "LayerSpec", "LevelSpec", "ParamSpec", "TransformSpec"]
