import shutil
from pathlib import Path

import click
from ape import project

PLUGIN_MANIFEST_FOLDER = project.path / "ape_safe" / "manifests"


@click.command()
@click.option("--override", is_flag=True)
def cli(override):
    for version in project.dependencies["safe-contracts"]:
        dependency = project.dependencies["safe-contracts"][version]
        plugin_manifest_path = PLUGIN_MANIFEST_FOLDER / f"safe-{version}.json"

        if plugin_manifest_path.is_file() and not override:
            click.echo(f"Version '{version}' already exists, skipping.'")
            continue

        # OK to delete - either doesn't exist or override set.
        plugin_manifest_path.unlink(missing_ok=True)

        click.echo(
            f"cp $HOME/{dependency.manifest_path.relative_to(Path.home())}"
            f" ./{plugin_manifest_path.relative_to(Path.cwd())}"
        )
        shutil.copyfile(dependency.manifest_path, plugin_manifest_path)
