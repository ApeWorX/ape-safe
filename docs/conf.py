extensions = ["sphinx_ape"]

doctest_global_setup = """
from sphinx_ape.build import BuildMode, DocumentationBuilder
from pathlib import Path
"""
