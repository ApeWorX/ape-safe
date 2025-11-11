from pathlib import Path

import click
import yaml  # type: ignore[import-untyped]
from ape import project
from ape.logging import logger

PLUGIN_MANIFEST_FOLDER = project.path / "ape_safe" / "manifests"

VERSIONS = {
    "v1.1.1": """
compile:
  exclude:
    - mocks
    - interfaces

dependencies:
  - name: openzeppelin
    github: OpenZeppelin/openzeppelin-contracts
    version: 2.2.0

solidity:
  version: 0.5.14
  import_remapping:
    - "@openzeppelin/contracts=openzeppelin/v2.2.0"
""",
    "v1.3.0": """
compile:
  exclude:
    - test
    - examples
    - interfaces

dependencies:
  - name: openzeppelin
    github: OpenZeppelin/openzeppelin-contracts
    version: 3.4.0

solidity:
  version: 0.7.6
  import_remapping:
    - "@openzeppelin/contracts=openzeppelin/v3.4.0"
""",
    "v1.4.1": """
compile:
  exclude:
    - test
    - examples
    - interfaces

dependencies:
  - name: openzeppelin
    github: OpenZeppelin/openzeppelin-contracts
    version: 3.4.0

solidity:
  version: 0.7.6
  import_remapping:
    - "@openzeppelin/contracts=openzeppelin/v3.4.0"
""",
}


def compile_version(version: str, override: bool):
    dependency = project.dependencies.install(
        name="safe-contracts",
        github="safe-global/safe-smart-account",
        version=version,
        config_override=yaml.safe_load(VERSIONS[version]),
    )
    plugin_manifest_path = PLUGIN_MANIFEST_FOLDER / f"safe-{version}.json"
    if not override and (plugin_manifest_path).is_file():
        logger.info(f"Version '{version}' already exists, skipping.'")
        return

    if not dependency.compiled:
        logger.warning(f"Safe {version} not compiled, compiling...")
        dependency.compile()

    logger.info(f"Writing './{plugin_manifest_path.relative_to(Path.cwd())}'")
    plugin_manifest_path.write_text(dependency.project.manifest.model_dump_json())


@click.command()
@click.option("--override", is_flag=True)
@click.argument(
    "versions",
    nargs=-1,
    type=click.Choice(list(VERSIONS)),
)
def cli(override, versions):
    """Build manifests for Safe protocol"""

    for version in iter(versions or VERSIONS):
        compile_version(version, override)
