"""Sphinx configuration for PyETWkit documentation."""

import sys
from pathlib import Path

# Add project source to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Project information
project = "PyETWkit"
copyright = "2025, m96-chan"
author = "m96-chan"

# Get version from package
try:
    from pyetwkit import __version__

    release = __version__
except ImportError:
    release = "1.0.0"

version = release

# Extensions
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx_autodoc_typehints",
    "myst_parser",
]

# Templates path
templates_path = ["_templates"]

# Exclude patterns
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# HTML theme
html_theme = "sphinx_rtd_theme"

# HTML static files path
html_static_path = ["_static"]

# Create _static directory if it doesn't exist
Path(__file__).parent.joinpath("_static").mkdir(exist_ok=True)

# Intersphinx mapping
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pandas": ("https://pandas.pydata.org/docs", None),
}

# Autodoc settings
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
}

autodoc_typehints = "description"
autodoc_type_aliases = {}

# Napoleon settings
napoleon_google_docstyle = True
napoleon_numpy_docstyle = True
napoleon_include_init_with_doc = True

# MyST settings
myst_enable_extensions = [
    "colon_fence",
    "deflist",
]

# Source suffix
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# Master document
master_doc = "index"
