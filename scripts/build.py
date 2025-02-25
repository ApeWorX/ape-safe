import shutil
from pathlib import Path

import click
from ape import project

PLUGIN_MANIFEST_FOLDER = project.path / "ape_safe" / "manifests"


@click.command()
def cli():
    for version in project.dependencies["safe-contracts"]:
        dependency = project.dependencies["safe-contracts"][version]
        plugin_manifest_path = PLUGIN_MANIFEST_FOLDER / f"safe-{version}.json"
        click.echo(
            f"cp $HOME/{dependency.manifest_path.relative_to(Path.home())}"
            f" ./{plugin_manifest_path.relative_to(Path.cwd())}"
        )
        shutil.copyfile(dependency.manifest_path, plugin_manifest_path)
