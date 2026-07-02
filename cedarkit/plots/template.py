from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cedarkit.plots.chart import Panel


class XYTemplate:
    def __init__(self):
        ...

    def render_panel(self, panel: "Panel"):
        raise NotImplementedError
