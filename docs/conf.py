# Sphinx 文档构建配置
#
# 完整参考：
# https://www.sphinx-doc.org/en/master/usage/configuration.html

from __future__ import annotations

from datetime import datetime
from importlib import metadata as importlib_metadata


# -- 项目信息 -------------------------------------------------------------

project = "cedarkit-plots"
author = "developers at cemc-oper"
copyright = f"{datetime.now():%Y}, {author}"

try:
    release = importlib_metadata.version("cedarkit-plots")
except importlib_metadata.PackageNotFoundError:
    release = "0.0.0"
version = ".".join(release.split(".")[:2])


# -- 通用配置 -------------------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "myst_nb",
    "sphinx_copybutton",
    "sphinx_design",
]

# MyST / MyST-NB
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "dollarmath",
    "linkify",
    "replacements",
    "smartquotes",
    "substitution",
    "tasklist",
]
myst_heading_anchors = 3

# 可执行 markdown / notebook 的默认行为：检测到改动则重新执行。
nb_execution_mode = "auto"
nb_execution_timeout = 180
nb_execution_allow_errors = False
nb_merge_streams = True
# 抑制绘图过程中可能产生的警告类 stderr 输出。
nb_output_stderr = "remove"

source_suffix = {
    ".md": "myst-nb",
    ".ipynb": "myst-nb",
    ".rst": "restructuredtext",
}
nb_render_markdown_format = "myst"

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "**.ipynb_checkpoints"]

language = "zh_CN"


# -- autodoc / autosummary -------------------------------------------------

autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}
autodoc_typehints = "description"
autosummary_generate = True
napoleon_numpy_docstring = True
napoleon_google_docstring = False


# -- intersphinx -----------------------------------------------------------

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "pandas": ("https://pandas.pydata.org/docs/", None),
    "xarray": ("https://docs.xarray.dev/en/stable/", None),
    "matplotlib": ("https://matplotlib.org/stable/", None),
    "cartopy": ("https://scitools.org.uk/cartopy/docs/latest/", None),
}


# -- HTML（sphinx-book-theme） ---------------------------------------------

html_theme = "sphinx_book_theme"
html_title = "cedarkit-plots"
html_static_path = ["_static"]

html_theme_options = {
    "repository_url": "https://github.com/cemc-oper/cedarkit-plots",
    "repository_branch": "main",
    "path_to_docs": "docs",
    "use_repository_button": True,
    "use_issues_button": True,
    "use_edit_page_button": True,
    "use_download_button": True,
    "home_page_in_toc": True,
    "show_navbar_depth": 2,
    "show_toc_level": 2,
    "navigation_with_keys": False,
}
