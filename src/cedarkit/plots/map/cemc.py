"""
CEMC 官方图片产品使用的中国区域底图，仅限 CEMC 内部使用

需要安装 cemc-meda-data 库，Metcode 地址 (仅 CEMC 内部访问，需要访问权限)

http://e.mc.met.cma/codingcorp/cedarkit/cemc-meda-data.git

如需使用，请联系 CEMC 获取。
"""
import importlib.resources
from pathlib import Path
from typing import Dict, List, Optional

from cartopy.io.shapereader import Reader
import cartopy.feature as cfeature
import cartopy.crs as ccrs

from . import MapType
from .default import DefaultMapLoader


MAP_PACKAGE_NAME = "cemc_meda_data"


class CemcMapLoader(DefaultMapLoader):
    def __init__(self, map_type: MapType = MapType.Portrait, **kwargs):
        super().__init__(map_type=map_type, **kwargs)
        self.projection = ccrs.PlateCarree()

        if map_type == MapType.Portrait:
            self.map_name = "portrait"
        elif map_type == MapType.SouthChinaSea:
            self.map_name = "landscape/NANHAI"
        elif map_type == MapType.Global:
            self.map_name = "global"
        else:
            raise ValueError(f"map type not supported: {map_type}")

        self.resource_base = str(importlib.resources.files(MAP_PACKAGE_NAME) / f"resources/maps/{self.map_name}")

        self.style = dict(
            g=dict(
                edgecolor="k",
                linewidth=1.5,
            ),
            gu=dict(
                edgecolor="k",
                linestyle=(0, (2, 1)),
                linewidth=1.5,
            ),
            gwd=dict(
                edgecolor="k",
                linestyle=(0, (5, 5)),
                linewidth=1.5,
            ),
            s=dict(
                edgecolor="k",
                linewidth=0.8,
            ),
            s2=dict(
                edgecolor="k",
                linestyle="--",
                linewidth=1.8,
            ),
            r=dict(
                edgecolor="dodgerblue",
                linewidth=1.5,
            ),
            h=dict(
                edgecolor="dodgerblue",
                linewidth=1.2,
            ),
            m=dict(
                edgecolor="dodgerblue"
            )
        )

    def update_style(self, name: str, style: Dict):
        self.style[name].update(style)

    def coastline(self, scale: Optional[str] = None, style: Optional[Dict] = None) -> List[cfeature.Feature]:
        features = super().coastline(scale=scale, style=style)
        return features

    def china_coastline(self, style: Optional[Dict] = None) -> List[cfeature.Feature]:
        shape_names = [
            dict(name="HAX", type="h"),         # 海岸线
            dict(name="HFCP_NH", type="h"),     # 南海岛屿岸线
        ]
        features = self.get_features(shape_names)
        return features

    def china_borders(self) -> List[cfeature.Feature]:
        shape_names = [
            dict(name="BOUL_G", type="g"),      # 陆地国界
        ]
        if self.map_type == MapType.Portrait:
            shape_names.append(
                dict(name="BOUL_GU", type="gu"),    # 未定国界
            )
        features = self.get_features(shape_names)

        return features

    def china_provinces(self) -> List[cfeature.Feature]:
        shape_names = [
            dict(name="BOUL_S", type="s"),      # 省界
            dict(name="BOUL_S2", type="s2"),    # 特别行政区界
        ]
        features = self.get_features(shape_names)

        return features

    def china_rivers(self) -> List[cfeature.Feature]:
        features = []

        if self.map_type == MapType.Portrait:
            shape_names = [
                dict(name="HYDL", type="r"),        # 主要河流
            ]
            features = self.get_features(shape_names)

        return features

    def china_nine_lines(self) -> List[cfeature.Feature]:
        shape_names = [
            dict(name="BOUL_JDX", type="g"),    # 南海断续线
        ]
        features = self.get_features(shape_names)

        return features

    def global_borders(self) -> List[cfeature.Feature]:
        shape_names = [
            dict(name="BOUL_G", type="g"),    # 国界
            dict(name="BOUL_Gwd", type="gwd"),    # 未定国界
        ]
        features = self.get_features_global(shape_names)

        return features

    def get_features(
            self, shape_names: List[Dict], projection: Optional[ccrs.Projection] = None
    ) -> List[cfeature.Feature]:
        if projection is None:
            projection = self.projection

        features = []
        for shape_item in shape_names:
            shape_name = shape_item["name"]
            feature_type = shape_item["type"]

            shape_file_name = Path(self.resource_base, f"{shape_name}.shp")
            reader = Reader(shape_file_name, encoding="GBK")
            feature_style = self.style[feature_type]
            feature = cfeature.ShapelyFeature(
                reader.geometries(),
                projection,
                facecolor="none",
                **feature_style
            )
            features.append(feature)

        return features

    def get_features_global(self, shape_names: List[Dict]) -> List[cfeature.Feature]:
        features = self.get_features(shape_names=shape_names, projection=ccrs.Mercator())
        return features


map_class = CemcMapLoader


def get_china_map() -> List[cfeature.Feature]:
    projection = ccrs.PlateCarree()
    shape_names = [
        dict(name="BOUL_G", type="g"),      # 陆地国界
        dict(name="BOUL_JDX", type="g"),    # 南海断续线
        dict(name="BOUL_GU", type="gu"),    # 未定国界
        dict(name="HAX", type="h"),         # 海岸线
        dict(name="BOUL_S", type="s"),      # 省界
        dict(name="BOUL_S2", type="s2"),    # 特别行政区界
        dict(name="HYDL", type="r"),        # 主要河流
        dict(name="HFCP_NH", type="h")      # 南海岛屿岸线
    ]
    features = []
    for shape_item in shape_names:
        shape_name = shape_item["name"]
        map_type = shape_item["type"]

        ref = importlib.resources.files(MAP_PACKAGE_NAME) / f"resources/maps/portrait/{shape_name}.shp"
        with importlib.resources.as_file(ref) as shape_file_name:
            reader = Reader(shape_file_name, encoding="GBK")
            feature_style = get_map_feature_style(map_type)
            feature = cfeature.ShapelyFeature(
                reader.geometries(),
                projection,
                facecolor="none",
                **feature_style
            )
            features.append(feature)

    return features


def get_china_nine_map() -> List[cfeature.Feature]:
    projection = ccrs.PlateCarree()
    shape_names = [
        dict(name="BOUL_G", type="g"),      # 陆地国界
        dict(name="BOUL_JDX", type="g"),    # 南海断续线
        dict(name="HAX", type="h"),         # 海岸线
        dict(name="BOUL_S", type="s"),      # 省界
        dict(name="BOUL_S2", type="s2"),    # 特别行政区界
        dict(name="HFCP_NH", type="h")      # 南海岛屿岸线
    ]
    features = []
    for shape_item in shape_names:
        shape_name = shape_item["name"]
        map_type = shape_item["type"]

        ref = importlib.resources.files(MAP_PACKAGE_NAME) / f"resources/maps/landscape/NANHAI/{shape_name}.shp"
        with importlib.resources.as_file(ref) as shape_file_name:
            reader = Reader(shape_file_name, encoding="GBK")
            feature_style = get_map_feature_style(map_type)
            feature = cfeature.ShapelyFeature(
                reader.geometries(),
                projection,
                facecolor="none",
                **feature_style
            )
            features.append(feature)

    return features


def get_map_feature_style(map_type: str) -> Dict:
    m = dict(
        g=dict(
            edgecolor="k",
            linewidth=1.5,
        ),
        gu=dict(
            edgecolor="k",
            linestyle=(0, (2, 1)),
            linewidth=1.5,
        ),
        s=dict(
            edgecolor="k",
            linewidth=0.8,
        ),
        s2=dict(
            edgecolor="k",
            linestyle="--",
            linewidth=1.8,
        ),
        r=dict(
            edgecolor="dodgerblue",
            linewidth=1.5,
        ),
        h=dict(
            edgecolor="dodgerblue",
            linewidth=1.2,
        ),
        m=dict(
            edgecolor="dodgerblue"
        )
    )
    return m[map_type]
