"""Map annotation drawing helpers used by the renderer."""

from __future__ import annotations

from typing import Any


def add_map_info_text(ax: Any, *, x: float, y: float, text: str) -> Any:
    """Draw the standard map review annotation in axes coordinates."""

    return ax.text(
        x,
        y,
        text,
        verticalalignment="bottom",
        horizontalalignment="right",
        transform=ax.transAxes,
        fontsize=3,
        bbox={
            "boxstyle": "round",
            "edgecolor": "black",
            "facecolor": "white",
            "linewidth": 0.5,
        },
    )
