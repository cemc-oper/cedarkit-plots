"""Value-only EnsCN collection presentation presets."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from cedarkit.plots.config import (
    BasemapSpec,
    Cell,
    ChartSelector,
    ColorbarSpec,
    DecorationSpec,
    LayoutSpec,
    MapFeatureSpec,
    Rect,
    SlotSpec,
    SubplotSpec,
    Theme,
)
from cedarkit.plots.domains.domain import Domain
from cedarkit.plots.domains.ens_cn_config import ENS_CN_DOMAIN
from cedarkit.plots.errors import ConfigError
from cedarkit.plots.map import MapType

from . import ChartTemplate, PanelTemplate


_DEFAULT_COLORBAR_ID = "ens_cn_colorbar"
_DEFAULT_COLORBAR_POSITION = Rect(
    space="figure",
    bounds=(.92, .15, .02, .7),
)


def _check_id(value: Any, name: str, *, allow_none: bool = False) -> str | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, str) or not value or any(char.isspace() for char in value):
        raise ConfigError(
            f"{name} must be a non-empty string without whitespace",
            code="invalid_template",
            path=(name,),
        )
    return value


def _check_role(value: Any, name: str, *, allow_none: bool = False) -> str | None:
    return _check_id(value, name, allow_none=allow_none)


def _check_columns(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ConfigError(
            "columns must be a positive integer",
            code="invalid_template",
            path=("columns",),
        )
    return value


def _check_rows(value: Any) -> int | str:
    if value == "auto":
        return value
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ConfigError(
            "rows must be a positive integer or 'auto'",
            code="invalid_template",
            path=("rows",),
        )
    return value


def _check_domain(value: Any) -> Domain:
    if not isinstance(value, Domain):
        raise ConfigError(
            "domain must be a Domain",
            code="invalid_template",
            path=("domain",),
        )
    return value


def _check_basemap(value: Any) -> BasemapSpec | None:
    if value is not None and not isinstance(value, BasemapSpec):
        raise ConfigError(
            "basemap must be BasemapSpec or None",
            code="invalid_template",
            path=("basemap",),
        )
    return value


def _check_position(value: Any, name: str) -> Cell | Rect:
    if not isinstance(value, (Cell, Rect)):
        raise ConfigError(
            f"{name} must be Cell or Rect",
            code="invalid_template",
            path=(name,),
        )
    return value


def _default_basemap() -> BasemapSpec:
    """Return the standard China map appearance without map annotations."""

    return BasemapSpec(
        map_type=MapType.Portrait,
        features=(
            MapFeatureSpec(
                name="coastline",
                kwargs={"scale": "50m", "style": {"linewidth": .5}},
            ),
            MapFeatureSpec(name="china_coastline"),
            MapFeatureSpec(name="china_borders"),
            MapFeatureSpec(name="china_provinces"),
            MapFeatureSpec(name="china_rivers"),
            MapFeatureSpec(name="china_nine_lines"),
        ),
        map_info=None,
    )


def ens_cn_chart(
    *,
    domain: Domain | None = None,
    basemap: BasemapSpec | None = None,
) -> ChartTemplate:
    """Return the reusable map presentation for one EnsCN Chart.

    The caller supplies the Chart and its member data.  This factory only
    declares the common domain and map appearance.
    """

    if domain is None:
        domain = ENS_CN_DOMAIN
    domain = _check_domain(domain)
    basemap = _check_basemap(basemap)
    if basemap is None:
        basemap = _default_basemap()
    return ChartTemplate(
        subplots={
            "main": SubplotSpec(
                kind="map",
                domain=domain,
                aspect="auto",
                basemap=basemap,
            ),
        },
    )


def ens_cn_layout(
    *,
    columns: int = 5,
    rows: int | str = "auto",
    control_id: str | None = None,
    max_id: str | None = None,
    control_position: Cell | None = None,
    max_position: Cell | None = None,
    control_role: str | None = "control",
    member_role: str | None = "member",
    max_role: str | None = "max",
    require_control: bool = True,
    require_max: bool = False,
    empty_slots: Mapping[str, Cell | Rect | SlotSpec] | None = None,
    colorbar_slot: tuple[str, Cell | Rect] | None = None,
) -> LayoutSpec:
    """Build ordinary layout configuration for caller-created Charts.

    Roles select existing Charts in creation order.  No selector creates a
    Chart, and MAX is optional unless ``require_max`` or ``max_id`` is used.
    """

    columns = _check_columns(columns)
    rows = _check_rows(rows)
    control_id = _check_id(control_id, "control_id", allow_none=True)
    max_id = _check_id(max_id, "max_id", allow_none=True)
    if control_position is not None and not isinstance(control_position, Cell):
        raise ConfigError(
            "control_position must be Cell or None",
            code="invalid_template",
            path=("control_position",),
        )
    if max_position is not None and not isinstance(max_position, Cell):
        raise ConfigError(
            "max_position must be Cell or None",
            code="invalid_template",
            path=("max_position",),
        )
    if control_position is not None and control_id is None:
        raise ConfigError(
            "control_position requires control_id",
            code="invalid_template",
            path=("control_position",),
        )
    if max_position is not None and max_id is None:
        raise ConfigError(
            "max_position requires max_id",
            code="invalid_template",
            path=("max_position",),
        )
    control_role = _check_role(control_role, "control_role", allow_none=True)
    member_role = _check_role(member_role, "member_role", allow_none=True)
    max_role = _check_role(max_role, "max_role", allow_none=True)
    if control_id is not None and control_id == max_id:
        raise ConfigError(
            "control_id and max_id cannot bind the same Chart",
            code="duplicate_binding",
            path=("layout", "placements"),
        )
    roles = [role for role in (control_role, member_role, max_role) if role is not None]
    if len(roles) != len(set(roles)):
        raise ConfigError(
            "control, member and max roles must be distinct",
            code="duplicate_binding",
            path=("layout", "order"),
        )

    placements: dict[str, Cell | Rect] = {}
    order: list[ChartSelector] = []
    if control_id is not None:
        placements[control_id] = control_position or Cell(row=0, column=0)
        order.append(ChartSelector(id=control_id, required=True))
    elif control_role is not None:
        order.append(ChartSelector(role=control_role, required=require_control))
    if max_id is not None:
        placements[max_id] = max_position or Cell(row=0, column=1)
        order.append(ChartSelector(id=max_id, required=True))
    elif max_role is not None:
        order.append(ChartSelector(role=max_role, required=require_max))
    if member_role is not None:
        order.append(ChartSelector(role=member_role, required=False))

    slots: dict[str, SlotSpec] = {}
    if empty_slots is not None:
        if not isinstance(empty_slots, Mapping):
            raise ConfigError(
                "empty_slots must be a mapping",
                code="invalid_template",
                path=("empty_slots",),
            )
        for raw_slot_id, position in empty_slots.items():
            slot_id = _check_id(raw_slot_id, "empty slot id")
            if slot_id in slots:
                raise ConfigError(
                    f"duplicate empty slot {slot_id!r}",
                    code="duplicate_binding",
                    path=("empty_slots", slot_id),
                )
            if isinstance(position, SlotSpec):
                slots[slot_id] = position
            else:
                slots[slot_id] = SlotSpec(position=_check_position(position, "empty_slots"))

    if colorbar_slot is not None:
        raw_slot_id, position = colorbar_slot
        slot_id = _check_id(raw_slot_id, "colorbar slot id")
        if slot_id in slots:
            raise ConfigError(
                f"colorbar slot {slot_id!r} conflicts with an empty slot",
                code="duplicate_binding",
                path=("colorbar_slot",),
            )
        slots[slot_id] = SlotSpec(
            position=_check_position(position, "colorbar_slot"),
            kind="colorbar",
        )

    return LayoutSpec(
        rows=rows,
        columns=columns,
        placements=placements,
        order=tuple(order),
        slots=slots,
    )


def ens_cn(
    *,
    columns: int = 5,
    rows: int | str = "auto",
    control_id: str | None = None,
    max_id: str | None = None,
    control_position: Cell | None = None,
    max_position: Cell | None = None,
    control_role: str | None = "control",
    member_role: str | None = "member",
    max_role: str | None = "max",
    require_control: bool = True,
    require_max: bool = False,
    domain: Domain | None = None,
    basemap: BasemapSpec | None = None,
    colorbar_id: str | None = _DEFAULT_COLORBAR_ID,
    colorbar_position: Rect | None = None,
    empty_slots: Mapping[str, Cell | Rect | SlotSpec] | None = None,
    colorbar_slot: tuple[str, Cell | Rect] | None = None,
) -> PanelTemplate:
    """Return an EnsCN PanelTemplate for already-created member Charts.

    The data workflow must create member and optional statistical MAX Charts
    and assign their roles.  This preset only orders and positions them.
    """

    layout = ens_cn_layout(
        columns=columns,
        rows=rows,
        control_id=control_id,
        max_id=max_id,
        control_position=control_position,
        max_position=max_position,
        control_role=control_role,
        member_role=member_role,
        max_role=max_role,
        require_control=require_control,
        require_max=require_max,
        empty_slots=empty_slots,
        colorbar_slot=colorbar_slot,
    )
    decorations = DecorationSpec()
    if colorbar_id is not None:
        colorbar_id = _check_id(colorbar_id, "colorbar_id")
        if colorbar_position is None:
            if colorbar_slot is None:
                colorbar_position = _DEFAULT_COLORBAR_POSITION
            else:
                slot_id, _ = colorbar_slot
                colorbar_position = Rect(
                    space="slot",
                    slot=slot_id,
                    bounds=(.1, .1, .8, .8),
                )
        if not isinstance(colorbar_position, Rect):
            raise ConfigError(
                "colorbar_position must be Rect or None",
                code="invalid_template",
                path=("colorbar_position",),
            )
        decorations = DecorationSpec(
            colorbars={colorbar_id: ColorbarSpec(position=colorbar_position)},
        )
    return PanelTemplate(
        layout=layout,
        theme=Theme(),
        chart_defaults=ens_cn_chart(domain=domain, basemap=basemap),
        decorations=decorations,
    )


__all__ = ["ens_cn", "ens_cn_chart", "ens_cn_layout"]
