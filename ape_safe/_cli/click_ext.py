import click
from ape import accounts
from ape.cli import ApeCliContextObject, ape_cli_context
from click import MissingParameter

from ape_safe.accounts import SafeContainer


class SafeCliContext(ApeCliContextObject):
    @property
    def safes(self) -> SafeContainer:
        # NOTE: Would only happen in local development of this plugin.
        assert "safe" in self.account_manager.containers, "Are all API methods implemented?"
        return self.account_manager.containers["safe"]


safe_cli_ctx = ape_cli_context(obj_type=SafeCliContext)


def _safe_callback(ctx, param, value):
    # NOTE: For some reason, the Cli CTX object is not the SafeCliCtx yet at this point.
    safes = accounts.containers["safe"]
    if value is None:
        # If there is only 1 safe, just use that.
        if len(safes) == 1:
            return next(safes.accounts)

        options = ", ".join(safes.aliases)
        raise MissingParameter(message=f"Must specify safe to use (one of '{options}').")

    else:
        return accounts.load(value)


safe_option = click.option("--safe", callback=_safe_callback)
