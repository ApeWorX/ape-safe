from typing import NoReturn, Sequence, Union, cast

import click
from ape import accounts, config
from ape.cli import ApeCliContextObject, ape_cli_context
from ape.exceptions import Abort
from click import BadOptionUsage, MissingParameter

from ape_safe.accounts import SafeContainer


class SafeCliContext(ApeCliContextObject):
    @property
    def safes(self) -> SafeContainer:
        # NOTE: Would only happen in local development of this plugin.
        assert "safe" in self.account_manager.containers, "Are all API methods implemented?"

        safe_container = self.account_manager.containers["safe"]
        return cast(SafeContainer, safe_container)

    def abort_txns_not_found(self, txn_ids: Sequence[Union[int, str]]) -> NoReturn:
        self.abort(f"Pending transaction(s) '{', '.join([f'{x}' for x in txn_ids])}' not found.")


def safe_cli_ctx():
    return ape_cli_context(obj_type=SafeCliContext)


def _safe_callback(ctx, param, value):
    # NOTE: For some reason, the Cli CTX object is not the SafeCliCtx yet at this point.
    safes = accounts.containers["safe"]
    if value is None:
        # First, check config for a default. If one is there,
        # we must use that.
        safe_config = config.get_config("safe")
        if alias := safe_config.default_safe:
            return accounts.load(alias)

        # If there is only 1 safe, just use that.
        elif len(safes) == 1:
            return next(safes.accounts)

        elif len(safes) == 0:
            raise Abort("First, add a safe account using command:\n\t`ape safe add`")

        options = ", ".join(safes.aliases)
        raise MissingParameter(message=f"Must specify one of '{options}').")

    elif value in safes.aliases:
        return accounts.load(value)

    else:
        raise BadOptionUsage("--safe", f"No safe with alias '{value}'")


safe_option = click.option("--safe", callback=_safe_callback)
safe_argument = click.argument("safe", callback=_safe_callback)


def _txn_ids_callback(ctx, param, value):
    value_ls = value or []
    return [int(x) if x.isnumeric() else x for x in value_ls if x]


txn_ids_argument = click.argument(
    "txn_ids", nargs=-1, callback=_txn_ids_callback, metavar="NONCE_OR_SAFE_TX_HASH(s)"
)
