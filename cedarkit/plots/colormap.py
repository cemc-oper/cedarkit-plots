import importlib.resources
import re
from typing import Optional, List

import numpy as np
import pandas as pd
import matplotlib.colors as mcolors


def get_ncl_colormap(
        name,
        index: Optional[np.ndarray] = None,
        count: Optional[int] = None,
        spread_start: Optional[int] = None,
        spread_end: Optional[int] = None,
        face_color="white"
) -> Optional[mcolors.ListedColormap]:
    """
    Generate Matplotlib colormap from NCL colormap files in resources directory.

    Parameters
    ----------
    name
        ncl color map name without extension.
    index
        color index to generate subset from original colormap, starting from 0.
    count
        color count, used with spread_start and spread_end.
    spread_start
        start index
    spread_end
        end index
    face_color
        add additional face color to colormap. default is white.
    Returns
    -------
    matplotlib.colors.ListedColormap
    """
    raw_colormap = _get_raw_ncl_colormap(name)
    if raw_colormap is None or (index is None and count is None):
        return raw_colormap

    if count is not None:
        # generate index
        total_colors = raw_colormap.N
        if spread_start is None:
            spread_start = 0
        if spread_end is None:
            spread_end = len(total_colors) - 1
        index = np.linspace(spread_start, spread_end, count, endpoint=True)
        index = np.array(np.round(index), dtype=int)

    colors = []
    if index[0] == -1:
        colors = [face_color]
        index = index[1:]
    raw_colors = raw_colormap(index)
    colors.extend(raw_colors)
    color_map = mcolors.ListedColormap(colors)
    return color_map


def _get_raw_ncl_colormap(name) -> Optional[mcolors.ListedColormap]:
    """
    Generate Matplotlib colormap from NCL color map files in resource directory.

    Parameters
    ----------
    name
        ncl color map name without extension.

    Returns
    -------
    matplotlib.colors.ListedColormap
    """
    color_map_path = None

    ref = importlib.resources.files("cedarkit.plots") / "resources/colormap/ncl"
    if color_map_path is None:
        with importlib.resources.as_file(ref / f"{name}.rgb") as file_path:
            if file_path.exists():
                color_map_path = file_path
    if color_map_path is None:
        with importlib.resources.as_file(ref / f"{name}.gp") as file_path:
            if file_path.exists():
                color_map_path = file_path

    if color_map_path is None:
        return None

    prog = re.compile(r"\s+(\d+)\s+(\d+)\s+(\d+)")
    with open(color_map_path, "r") as f:
        buff = f.read()
        r = prog.findall(buff)
        rgbs = np.asarray(r, dtype="i4") / 255
        color_map = mcolors.ListedColormap(rgbs, name)
        return color_map


def generate_colormap_using_ncl_colors(color_names: List[str], name: str) -> mcolors.ListedColormap:
    """
    Use NCL named colors to generate a colormap.

    Parameters
    ----------
    color_names
        color names list. ignore the case.
    name
        colormap name

    Returns
    -------
    matplotlib.colors.ListedColormap
    """
    color_map_dir = importlib.resources.files("cedarkit.plots") / "resources/colormap/ncl"
    with importlib.resources.as_file(color_map_dir / f"ncl_colors.csv") as color_names_csv:
        df = pd.read_csv(color_names_csv)
        df["name"] = df["name"].str.lower()
        rgbs = []
        for color_name in color_names:
            color_name = color_name.lower()
            if color_name == "transparent":
                rgbs.append([1, 1, 1, 1])
                continue
            color_record = df[df["name"] == color_name].iloc[0]
            rgbs.append(color_record[["R", "G", "B"]].values/255)

        color_map = mcolors.ListedColormap(rgbs, name)
        return color_map
