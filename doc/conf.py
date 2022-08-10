# pylint: disable=redefined-builtin
# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import builtins
import os
import sys

import sphinx_rtd_theme  # pylint: disable=unused-import

builtins.__sphinx_build__ = True

sys.path.insert(0, os.path.abspath("../.out/bdist/lib/python3.8/site-packages"))
sys.path.insert(0, os.path.abspath("../.out/bdist/local/lib/python3.8/site-packages"))

# -- Project information -----------------------------------------------------

project = "MATE"
copyright = "2019-2022, The MATE Team"
author = "The MATE Team"

# The full version, including alpha/beta/rc tags
release = "0.1.0.0"


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.autosummary",
    "sphinxcontrib.autoprogram",
    "sphinx_paramlinks",
    "sphinx_rtd_theme",
]

autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}

autodoc_typehints = "both"

autosummary_generate = True
autosectionlabel_prefix_document = True

default_role = "any"

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# We generate some of these and copy them in.
suppress_warnings = ["image.not_readable"]


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#

html_theme = "sphinx_rtd_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = []

# -- Extension configuration -------------------------------------------------
