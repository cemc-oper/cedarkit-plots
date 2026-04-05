import warnings

from typing import TYPE_CHECKING, Dict, Optional
from dataclasses import dataclass, field

from cedarkit.maps.map import MapLoader
from cedarkit.maps.util import add_map_info_text

if TYPE_CHECKING:
    from cedarkit.maps.chart import Layer


@dataclass
class MapFeatureConfig:
    """
    Attributes
    ----------
    loader
        options for MapLoader's map methods to get map features.
    render
        auto render in render_layer methods.
    """
    loader: Optional[Dict] = None
    render: bool = False


@dataclass
class MapInfo:
    text: str
    x: float
    y: float


@dataclass
class MapPainter:
    """
    Paint map on Layer, including map features and map info text.
    """
    map_loader: MapLoader
    coastline_config: MapFeatureConfig = field(default_factory=MapFeatureConfig)
    land_config: MapFeatureConfig = field(default_factory=MapFeatureConfig)
    rivers_config: MapFeatureConfig = field(default_factory=MapFeatureConfig)
    lakes_config: MapFeatureConfig = field(default_factory=MapFeatureConfig)
    china_coastline_config: MapFeatureConfig = field(default_factory=MapFeatureConfig)
    china_borders_config: MapFeatureConfig = field(default_factory=MapFeatureConfig)
    china_provinces_config: MapFeatureConfig = field(default_factory=MapFeatureConfig)
    china_rivers_config: MapFeatureConfig = field(default_factory=MapFeatureConfig)
    china_nine_lines_config: MapFeatureConfig = field(default_factory=MapFeatureConfig)
    global_borders_config: MapFeatureConfig = field(default_factory=MapFeatureConfig)
    map_info: Optional[MapInfo] = None

    def render_layer(self, layer: "Layer"):
        """
        Render map on layer according to configs.

        Parameters
        ----------
        layer
        """
        if self.coastline_config.render:
            self.coastline(layer=layer)
        if self.land_config.render:
            self.land(layer=layer)
        if self.rivers_config.render:
            self.rivers(layer=layer)
        if self.lakes_config.render:
            self.lakes(layer=layer)
        if self.china_coastline_config.render:
            self.china_coastline(layer=layer)
        if self.china_borders_config.render:
            self.china_borders(layer=layer)
        if self.china_provinces_config.render:
            self.china_provinces(layer=layer)
        if self.china_rivers_config.render:
            self.china_rivers(layer=layer)
        if self.china_nine_lines_config.render:
            self.china_nine_lines(layer=layer)
        if self.global_borders_config.render:
            self.global_borders(layer=layer)

    def coastline(self, layer: "Layer"):
        fs = self.map_loader.coastline(**self.coastline_config.loader)
        self.add_features_to_layer(layer=layer, features=fs)

    def land(self, layer: "Layer"):
        fs = self.map_loader.land(**self.land_config.loader)
        self.add_features_to_layer(layer=layer, features=fs)

    def rivers(self, layer: "Layer"):
        fs = self.map_loader.rivers(**self.rivers_config.loader)
        self.add_features_to_layer(layer=layer, features=fs)

    def lakes(self, layer: "Layer"):
        fs = self.map_loader.lakes(**self.lakes_config.loader)
        self.add_features_to_layer(layer=layer, features=fs)

    def china_coastline(self, layer: "Layer"):
        fs = self.map_loader.china_coastline()
        self.add_features_to_layer(layer=layer, features=fs)

    def china_borders(self, layer: "Layer"):
        fs = self.map_loader.china_borders()
        self.add_features_to_layer(layer=layer, features=fs)

    def china_provinces(self, layer: "Layer"):
        fs = self.map_loader.china_provinces()
        self.add_features_to_layer(layer=layer, features=fs)

    def china_rivers(self, layer: "Layer"):
        fs = self.map_loader.china_rivers()
        self.add_features_to_layer(layer=layer, features=fs)

    def china_nine_lines(self, layer: "Layer"):
        fs = self.map_loader.china_nine_lines()
        self.add_features_to_layer(layer=layer, features=fs)

    def global_borders(self, layer: "Layer"):
        fs = self.map_loader.global_borders()
        self.add_features_to_layer(layer=layer, features=fs)

    def add_map_info(self, layer: "Layer"):
        """
        Add map info text box into layer.

        Parameters
        ----------
        layer
        """
        if self.map_info is None:
            warnings.warn("map_info is None, ignored.")
            return

        ax = layer.ax
        add_map_info_text(
            ax=ax,
            x=self.map_info.x,
            y=self.map_info.y,
            text=self.map_info.text,
        )

    @classmethod
    def add_features_to_layer(cls, layer: "Layer", features):
        """
        Add map features to layer.

        Parameters
        ----------
        layer
        features
        """
        ax = layer.ax
        for f in features:
            ax.add_feature(
                f,
                # zorder=100,
            )


