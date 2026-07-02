from typing import Tuple, NamedTuple
from dataclasses import dataclass
import math
import sys


@dataclass
class LevelSetting:
    min_value: float
    max_value: float
    step: float


def calculate_levels_automatic(min_value: float, max_value: float, max_count: int, outside: bool) -> LevelSetting:
    """
    calculate levels from min value and max value.

    Algorithm and codes are copied from NCL source code (_NhlGetEndpointsAndStepSize function in ni/src/lib/hlu/nicevals.c).

    References
    -----------
    NCL source code

    Parameters
    ----------
    min_value
    max_value
    max_count
    outside

    Returns
    -------
    LevelSetting
    """
    assert min_value < max_value

    tables = [1.0, 2.0, 2.5, 4.0, 5.0, 10.0, 20.0, 25.0, 40.0, 50.0, 100.0, 200.0, 250.0, 400.0, 500.0]
    final_min = 0.0
    final_max = 0.0

    count = len(tables)

    # 计算得到一个合适的系数，与表中数值相乘作为可选步长
    d = math.pow(10.0, math.floor(math.log10(max_value - min_value)) - 2)

    max_float = sys.float_info.max
    step_size = sys.float_info.max

    if outside:
        min_func = math.floor
        max_func = math.ceil
    else:
        min_func = math.ceil
        max_func = math.floor

    for i in range(count):
        current_step_size = tables[i] * d

        # 根据当前步长计算取值范围
        current_min = min_func(min_value / current_step_size) * current_step_size
        current_max = max_func(max_value / current_step_size) * current_step_size

        # 更新最值和步长条件：
        #   1. 最终步长 step_size 未赋值，即为最大浮点数
        #   2. 当前步长 current_step_size 小于等于最终步长 step_size，且当前层次个数小于 max_steps - 1
        if (
                ((i >= count - 1) and (step_size == max_float))
                or
                (
                        (current_step_size <= step_size)
                        and
                        (float((current_max - current_min) / current_step_size) <= (float(max_count - 1)))
                )
        ):
            step_size = current_step_size
            final_max = current_max
            final_min = current_min

    return LevelSetting(min_value=final_min, max_value=final_max, step=step_size)
