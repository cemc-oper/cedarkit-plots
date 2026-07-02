from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("cedarkit.plots")
except PackageNotFoundError:
    # package is not installed
    pass
