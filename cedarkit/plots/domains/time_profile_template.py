from typing import TYPE_CHECKING, List, Callable

import pandas as pd
import numpy as np

from cedarkit.plots.template import XYTemplate

if TYPE_CHECKING:
    from cedarkit.plots.chart import Panel, Layer


class TimeStepAndLevelXYTemplate(XYTemplate):
    """


            ------------------
            |                |
            |                |
      level |                |
            |                |
            |                |
            ------------------
                 Time step

    """
    def __init__(self, steps: List[float], levels: List[float], start_time: pd.Timestamp):
        super().__init__()
        self.steps = steps
        self.levels = levels
        self.start_time = start_time

    def render_panel(self, panel: "Panel"):
        chart = panel.add_chart(domain=self)

        fig = chart.fig
        ax = fig.add_axes(
            (0.1, 0.1, 0.8, 0.8)
        )
        layer = Layer(projection=None, chart=chart)
        layer.set_axes(ax)

        ax.set_xticks(np.arange(0, self.steps[-1] + 1, 12))
        ax.set_yticks(self.levels)
        x_format = TimeStepAndLevelXYTemplate.create_x_formatter(
            last_step=self.steps[-1],
            start_time=self.start_time,
        )
        ax.xaxis.set_major_formatter(x_format)

    @staticmethod
    def create_x_formatter(last_step: float, start_time: pd.Timestamp) -> Callable[[float, int], str]:
        def x_format(x: float, pos: int) -> str:
            valid_time = start_time + pd.Timedelta(hours=x)

            label = valid_time.strftime("%HZ")
            if label == "00Z":
                label += f"\n{valid_time.strftime('%d%b').upper()}"
            if x == last_step:
                label += f"\n{valid_time.strftime('%Y')}"
            return label

        return x_format

