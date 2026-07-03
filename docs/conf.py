"""Sphinx configuration for macon documentation."""

project = "macon"
copyright = "2024, Eric Charles"
author = "Eric Charles"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx_autodoc_typehints",
    "autoapi.extension",
    "sphinx_click",
    "sphinx_rtd_theme",
]

# -- sphinx-autoapi configuration -------------------------------------------
autoapi_type = "python"
autoapi_dirs = ["../src/macon"]
autoapi_ignore = ["*/__pycache__/*", "*/_version.py"]
autoapi_options = [
    "members",
    "undoc-members",
    "show-inheritance",
    "show-module-summary",
    "imported-members",
]
autoapi_keep_files = True

# -- Napoleon (numpy docstrings) --------------------------------------------
napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_use_param = True
napoleon_use_rtype = False

# -- autodoc settings -------------------------------------------------------
autodoc_typehints = "signature"
autodoc_member_order = "bysource"

# -- intersphinx mapping ----------------------------------------------------
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "sqlalchemy": ("https://docs.sqlalchemy.org/en/20/", None),
    "pydantic": ("https://docs.pydantic.dev/latest/", None),
    "fastapi": ("https://fastapi.tiangolo.com/", None),
    "click": ("https://click.palletsprojects.com/en/8.x/", None),
}

# -- General configuration --------------------------------------------------
templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- HTML output -------------------------------------------------------------
html_theme = "sphinx_rtd_theme"
html_theme_options = {
    "navigation_depth": 4,
    "collapse_navigation": False,
}
html_static_path = ["_static"]
