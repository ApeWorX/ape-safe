#!/usr/bin/env python
from setuptools import find_packages, setup

extras_require = {
    "test": [  # `test` GitHub Action jobs uses this
        "pytest>=6.0",  # Core testing package
        "pytest-xdist",  # multi-process runner
        "pytest-cov",  # Coverage analyzer plugin
        "hypothesis>=6.2.0,<7.0",  # Strategy-based fuzzer
        "ape-foundry>=0.8",  # Used as the testing provider
        "ape-solidity>=0.8",  # Needed for compiling the Safe contracts
    ],
    "lint": [
        "black>=24.10.0,<25",  # Auto-formatter and linter
        "mypy>=1.13.0,<2",  # Static type analyzer
        "types-requests",  # Needed for mypy type shed
        "types-setuptools",  # Needed for mypy type shed
        "flake8>=7.1.1,<8",  # Style linter
        "flake8-breakpoint>=1.1.0,<2",  # Detect breakpoints left in code
        "flake8-print>=4.0.1,<5",  # Detect print statements left in code
        "flake8-pydantic",  # For detecting issues with Pydantic models
        "flake8-type-checking",  # Detect imports to move in/out of type-checking blocks
        "isort>=5.13.2,<6",  # Import sorting linter
        "mdformat>=0.7.18,<0.8",  # Docs formatter and linter
        "mdformat-pyproject>=0.0.1",  # Allows configuring in pyproject.toml
    ],
    "release": [  # `release` GitHub Action job uses this
        "setuptools",  # Installation tool
        "wheel",  # Packaging tool
        "twine==3.8.0",  # Package upload tool
    ],
    "dev": [
        "commitizen",  # Manage commits and publishing releases
        "pre-commit",  # Ensure that linters are run prior to committing
        "pytest-watch",  # `ptw` test watcher/runner
        "IPython",  # Console for interacting
        "ipdb",  # Debugger (Must use `export PYTHONBREAKPOINT=ipdb.set_trace`)
    ],
}

# NOTE: `pip install -e .[dev]` to install package
extras_require["dev"] = (
    extras_require["test"]
    + extras_require["lint"]
    + extras_require["release"]
    + extras_require["dev"]
)

with open("./README.md") as readme:
    long_description = readme.read()


setup(
    name="ape-safe",
    use_scm_version=True,
    setup_requires=["setuptools_scm"],
    description="""ape-safe: Gnosis Safe account plugin for Ape""",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="ApeWorX Ltd.",
    author_email="admin@apeworx.io",
    url="https://github.com/ApeWorX/ape-safe",
    include_package_data=True,
    install_requires=[
        "eth-ape>=0.8.14,<0.9",
        "requests>=2.31.0,<3",
        "eip712",  # Use same version as eth-ape
        "click",  # Use same version as eth-ape
        "pydantic",  # Use same version as eth-ape
        "eth-utils",  # Use same version as eth-ape
    ],
    entry_points={
        "ape_cli_subcommands": [
            "ape_safe=ape_safe._cli:cli",
        ],
    },
    python_requires=">=3.9,<4",
    extras_require=extras_require,
    py_modules=["ape_safe"],
    license="Apache-2.0",
    zip_safe=False,
    keywords="ethereum",
    packages=find_packages(exclude=["tests", "tests.*"]),
    package_data={"ape_safe": ["py.typed", "manifests/*"]},
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Natural Language :: English",
        "Operating System :: MacOS",
        "Operating System :: POSIX",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
