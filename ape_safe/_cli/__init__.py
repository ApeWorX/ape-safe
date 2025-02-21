import click

from ape_safe._cli.pending import pending
from ape_safe._cli.safe_mgmt import _list, add, all_txns, remove

try:
    from ape_safe._cli.host_api import host
except ImportError:
    host = None  # type: ignore[assignment]


@click.group(short_help="Manage Safe accounts and view Safe API data")
def cli():
    """
    Command-line helper for managing Safes. You can add Safes to your local accounts,
    or view data from any Safe using the Safe API client.
    """


cli.add_command(_list)
cli.add_command(add)
cli.add_command(remove)
cli.add_command(all_txns)
cli.add_command(pending)
if host:
    cli.add_command(host)
