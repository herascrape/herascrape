"""Sphinx build of the herascrape Python client reference.

Narrative pages are MyST markdown; the reference pages are autodoc over the
installed package, so the docs need `herascrape` importable.
"""

from importlib.metadata import version as installed_version

project = "herascrape"
author = "herascrape"
copyright = "herascrape"
release = installed_version("herascrape")
version = release

extensions = [
    "sphinx.ext.autodoc",
    "myst_parser",
    "sphinx_copybutton",
    "sphinxext.opengraph",
]

exclude_patterns = ["_build"]

# Single backticks are code, which is what every docstring in the package means
# by them.
default_role = "literal"

myst_heading_anchors = 3
myst_enable_extensions = ["substitution"]
myst_substitutions = {"release": release}

autodoc_default_options = {
    "members": True,
    "show-inheritance": True,
}
autodoc_member_order = "bysource"
autodoc_preserve_defaults = True
autodoc_typehints = "signature"

html_theme = "furo"
# Keyword-bearing and stable: it is the <title> of the landing page and the
# suffix of every other one.
html_title = "herascrape Python client"
html_baseurl = "https://herascrape.readthedocs.io/en/latest/"
html_show_sphinx = False
html_copy_source = False
html_theme_options = {
    "source_repository": "https://github.com/herascrape/herascrape/",
    "source_branch": "main",
    "source_directory": "python/docs/",
}

ogp_site_url = html_baseurl
ogp_site_name = "herascrape Python client"
ogp_description_length = 200
# Cards need matplotlib, which is not worth pinning into a docs build.
ogp_social_cards = {"enable": False}
