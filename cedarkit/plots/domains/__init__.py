import inspect
from typing import Union, Type

from .map_template import MapTemplate, SubMapConfig
from .east_asia import EastAsiaMapTemplate, CnAreaMapTemplate
from .north_polar import NorthPolarMapTemplate
from .europe_asia import EuropeAsiaMapTemplate
from .global_template import GlobalMapTemplate, GlobalAreaMapTemplate
from .ens_cn import EnsCNMapTemplate
from .time_profile_template import TimeStepAndLevelXYTemplate


# def parse_domain(domain: Union[str, Type[XYTemplate], XYTemplate]) -> XYTemplate:
#     if inspect.isclass(domain):
#         d = domain()
#     elif isinstance(domain, XYTemplate):
#         d = domain
#     elif isinstance(domain, str):
#         if domain == "cemc.east_asia":
#             d = EastAsiaMapTemplate()
#         elif domain == "cemc.cn_area":
#             d = CnAreaMapTemplate()
#         else:
#             raise ValueError(f"invalid domain: {domain}")
#     else:
#         raise TypeError(f"invalid domain type")
#
#     return d
