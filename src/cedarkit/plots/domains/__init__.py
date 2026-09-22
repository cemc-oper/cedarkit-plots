import inspect
from typing import Union, Type

from .domain import Domain


_LAZY_EXPORTS = {
    "MapTemplate": (".map_template", "MapTemplate"),
    "SubMapConfig": (".map_template", "SubMapConfig"),
    "EastAsiaMapTemplate": (".east_asia", "EastAsiaMapTemplate"),
    "CnAreaMapTemplate": (".east_asia", "CnAreaMapTemplate"),
    "NorthPolarMapTemplate": (".north_polar", "NorthPolarMapTemplate"),
    "EuropeAsiaMapTemplate": (".europe_asia", "EuropeAsiaMapTemplate"),
    "GlobalMapTemplate": (".global_template", "GlobalMapTemplate"),
    "GlobalAreaMapTemplate": (".global_template", "GlobalAreaMapTemplate"),
    "EnsCNMapTemplate": (".ens_cn", "EnsCNMapTemplate"),
    "TimeStepAndLevelXYTemplate": (".time_profile_template", "TimeStepAndLevelXYTemplate"),
    "EAST_ASIA_DOMAIN": (".east_asia_config", "EAST_ASIA_DOMAIN"),
    "SOUTH_CHINA_SEA_DOMAIN": (".east_asia_config", "SOUTH_CHINA_SEA_DOMAIN"),
    "ENS_CN_DOMAIN": (".ens_cn_config", "ENS_CN_DOMAIN"),
    "CN_AREA": (".remaining_config", "CN_AREA"),
    "CN_AREA_DOMAIN": (".remaining_config", "CN_AREA_DOMAIN"),
    "CN_DOMAIN": (".remaining_config", "CN_DOMAIN"),
    "EUROPE_ASIA_AREA": (".remaining_config", "EUROPE_ASIA_AREA"),
    "EUROPE_ASIA_DOMAIN": (".remaining_config", "EUROPE_ASIA_DOMAIN"),
    "GLOBAL_AREA": (".remaining_config", "GLOBAL_AREA"),
    "GLOBAL_DOMAIN": (".remaining_config", "GLOBAL_DOMAIN"),
    "NORTH_POLAR_AREA": (".remaining_config", "NORTH_POLAR_AREA"),
    "NORTH_POLAR_DOMAIN": (".remaining_config", "NORTH_POLAR_DOMAIN"),
}


def __getattr__(name):
    """Load legacy template classes only when an old entry point asks for one."""

    try:
        module_name, attribute = _LAZY_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    from importlib import import_module

    value = getattr(import_module(module_name, __name__), attribute)
    globals()[name] = value
    return value


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


__all__ = [
    "CnAreaMapTemplate",
    "CN_AREA",
    "CN_AREA_DOMAIN",
    "CN_DOMAIN",
    "Domain",
    "EAST_ASIA_DOMAIN",
    "ENS_CN_DOMAIN",
    "EastAsiaMapTemplate",
    "EnsCNMapTemplate",
    "EUROPE_ASIA_AREA",
    "EUROPE_ASIA_DOMAIN",
    "EuropeAsiaMapTemplate",
    "GlobalAreaMapTemplate",
    "GLOBAL_AREA",
    "GLOBAL_DOMAIN",
    "GlobalMapTemplate",
    "MapTemplate",
    "NORTH_POLAR_AREA",
    "NORTH_POLAR_DOMAIN",
    "NorthPolarMapTemplate",
    "SubMapConfig",
    "SOUTH_CHINA_SEA_DOMAIN",
    "TimeStepAndLevelXYTemplate",
]
