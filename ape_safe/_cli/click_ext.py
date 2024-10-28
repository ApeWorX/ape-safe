from collections.abc import Sequence
from typing import TYPE_CHECKING, NoReturn, Optional, Union, cast

import click
from ape.cli import ApeCliContextObject, ape_cli_context
from ape.exceptions import Abort
from click import BadOptionUsage, MissingParameter

if TYPE_CHECKING:
    # perf: Keep the CLI module loading fast as possible.
    from ape.api import AccountAPI

    from ape_safe.accounts import SafeContainer


class SafeCliContext(ApeCliContextObject):
    @property
    def safes(self) -> "SafeContainer":
        # NOTE: Would only happen in local development of this plugin.
        assert "safe" in self.account_manager.containers, "Are all API methods implemented?"

        from ape_safe.accounts import SafeContainer

        safe_container = self.account_manager.containers["safe"]
        return cast(SafeContainer, safe_container)

    def abort_txns_not_found(self, txn_ids: Sequence[Union[int, str]]) -> NoReturn:
        self.abort(f"Pending transaction(s) '{', '.join([f'{x}' for x in txn_ids])}' not found.")


def safe_cli_ctx():
    return ape_cli_context(obj_type=SafeCliContext)


def _txn_ids_callback(ctx, param, value):
    value_ls = value or []
    return [int(x) if x.isnumeric() else x for x in value_ls if x]


txn_ids_argument = click.argument(
    "txn_ids", nargs=-1, callback=_txn_ids_callback, metavar="NONCE_OR_SAFE_TX_HASH(s)"
)


class CallbackFactory:
    """
    Helper class to prevent circular import and have access
    to Ape objects.
    """

    @classmethod
    def safe_callback(cls, ctx, param, value):
        from ape.utils import ManagerAccessMixin as access

        # NOTE: For some reason, the Cli CTX object is not the SafeCliCtx yet at this point.
        safes = access.account_manager.containers["safe"]
        if value is None:
            # First, check config for a default. If one is there,
            # we must use that.
            safe_config = access.config_manager.get_config("safe")
            if alias := safe_config.default_safe:
                return access.account_manager.load(alias)

            # If there is only 1 safe, just use that.
            elif len(safes) == 1:
                return next(safes.accounts)

            elif len(safes) == 0:
                raise Abort("First, add a safe account using command:\n\t`ape safe add`")

            options = ", ".join(safes.aliases)
            raise MissingParameter(message=f"Must specify one of '{options}').")

        elif value in safes.aliases:
            return access.account_manager.load(value)

        else:
            raise BadOptionUsage("--safe", f"No safe with alias '{value}'")

    @classmethod
    def submitter_callback(cls, ctx, param, val):
        if val is None:
            return None

        from ape.utils import ManagerAccessMixin as access

        if val in access.account_manager.aliases:
            return access.account_manager.load(val)

        # Account address - execute using this account.
        elif val in access.account_manager:
            return access.account_manager[val]

        # Saying "yes, execute". Use first "local signer".
        elif val.lower() in ("true", "t", "1"):
            safe = access.account_manager.load(ctx.params["alias"])
            if not safe.local_signers:
                ctx.obj.abort("Cannot use `--execute TRUE` without a local signer.")

            return safe.select_signer(for_="submitter")

        return None

    @classmethod
    def sender_callback(cls, ctx, param, val) -> Optional[Union["AccountAPI", bool]]:
        """
        Either returns the account or ``False`` meaning don't execute.
        NOTE: The handling of the `--execute` flag in the `pending` CLI
        all happens here EXCEPT if a pending tx is executable and no
        value of `--execute` was provided.
        """
        return cls._get_execute_callback(ctx, param, val, name="sender")

    @classmethod
    def execute_callback(cls, ctx, param, val) -> Optional[Union["AccountAPI", bool]]:
        """
        Either returns the account or ``False`` meaning don't execute.
        """
        return cls._get_execute_callback(ctx, param, val)

    @classmethod
    def _get_execute_callback(cls, ctx, param, val, name: str = "execute"):
        if val is None:
            # Was not given any value.
            # If it is determined in `pending` that a tx can execute,
            # the user will get prompted.
            # Avoid this by always doing `--execute false`.
            return None

        elif submitter := cls.submitter_callback(ctx, param, val):
            return submitter

        # Saying "no, do not execute", even if we could.
        elif val.lower() in ("false", "f", "0"):
            return False

        raise BadOptionUsage(
            f"--{name}", f"`--{name}` value '{val}` not a boolean or account identifier."
        )


callback_factory = CallbackFactory()
safe_option = click.option("--safe", callback=callback_factory.safe_callback)
safe_argument = click.argument("safe", callback=callback_factory.safe_callback)
submitter_option = click.option(
    "--submitter", help="Account to execute", callback=callback_factory.submitter_callback
)
sender_option = click.option("--sender", callback=callback_factory.sender_callback)
execute_option = click.option("--execute", callback=callback_factory.execute_callback)
