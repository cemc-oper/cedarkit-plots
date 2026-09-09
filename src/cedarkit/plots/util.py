import matplotlib.axes


def clear_xarray_plot_components(ax: matplotlib.axes.Axes):
    """
    清除 Xarray 自动绘图生成的图片组件，包括：

    * 标题
    * X轴标签
    * Y轴标签

    Parameters
    ----------
    ax
    """
    ax.set_title("")
    ax.set_xlabel("")
    ax.set_ylabel("")
    return ax


def clear_axes(ax: matplotlib.axes.Axes):
    """
    隐藏坐标轴、边框线、坐标短线、坐标标签
    """
    ax.axis('off')
