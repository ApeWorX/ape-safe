from contextlib import ContextDecorator
from typing import TYPE_CHECKING, Optional

from ape.exceptions import AccountsError, ApeException, ContractLogicError, SignatureError

if TYPE_CHECKING:
    from ape.types import AddressType
    from requests import Response


class ApeSafeException(ApeException):
    pass


class ApeSafeError(ApeSafeException, AccountsError):
    """
    An error to raise in place of AccountsError for the ``ape-safe`` plugin.
    """


class NotASigner(ApeSafeException):
    def __init__(self, signer: "AddressType"):
        super().__init__(f"{signer} is not a valid signer.")


class NoLocalSigners(ApeSafeException, SignatureError):
    def __init__(self):
        super().__init__("No local signers available, try resubmitting with `submitter=` kwarg.")


class NotEnoughSignatures(ApeSafeException, SignatureError):
    def __init__(self, expected: int, actual: int):
        super().__init__(
            f"Not enough signatures, {expected - actual} more are needed. Bypass this behavior"
            " and publish to Safe API by adding 'submit_transaction=False' to your call."
        )


class ClientUnavailable(ApeSafeException):
    def __init__(self, message: Optional[str] = None) -> None:
        super().__init__(message or "Client unavailable.")


SAFE_ERROR_CODES = {
    "GS000": "Could not finish initialization",
    "GS001": "Threshold needs to be defined",
    "GS010": "Not enough gas to execute Safe transaction",
    "GS011": "Could not pay gas costs with ether",
    "GS012": "Could not pay gas costs with token",
    "GS013": "Safe transaction failed when gasPrice and safeTxGas were 0",
    "GS020": "Signatures data too short",
    "GS021": "Invalid contract signature location: inside static part",
    "GS022": "Invalid contract signature location: length not present",
    "GS023": "Invalid contract signature location: data not complete",
    "GS024": "Invalid contract signature provided",
    "GS025": "Hash has not been approved",
    "GS026": "Invalid owner provided",
    "GS030": "Only owners can approve a hash",
    "GS031": "Method can only be called from this contract",
    "GS100": "Modules have already been initialized",
    "GS101": "Invalid module address provided",
    "GS102": "Module has already been added",
    "GS103": "Invalid prevModule, module pair provided",
    "GS104": "Method can only be called from an enabled module",
    "GS105": "Invalid starting point for fetching paginated modules",
    "GS106": "Invalid page size for fetching paginated modules",
    "GS200": "Owners have already been set up",
    "GS201": "Threshold cannot exceed owner count",
    "GS202": "Threshold needs to be greater than 0",
    "GS203": "Invalid owner address provided",
    "GS204": "Address is already an owner",
    "GS205": "Invalid prevOwner, owner pair provided",
    "GS300": "Guard does not implement IERC165",
}


class SafeLogicError(ApeSafeException, ContractLogicError):
    def __init__(self, error_code: str):
        super().__init__(f"{SAFE_ERROR_CODES[error_code]} ({error_code})")


class handle_safe_logic_error(ContextDecorator):
    def __enter__(self):
        pass

    def __exit__(self, exc_type: type[BaseException], exc: BaseException, tb):
        if (
            isinstance(exc, ContractLogicError)  # NOTE: Just for mypy
            and exc_type == ContractLogicError
        ):
            message = exc.message.replace("revert: ", "").strip()
            if message.startswith("GS") and message in SAFE_ERROR_CODES:
                raise SafeLogicError(exc.message.replace("revert: ", "")) from exc

        # NOTE: Will raise `exc` by default because we did not return anything


class MulticallException(ApeSafeException):
    pass


class ValueRequired(MulticallException):
    def __init__(self, amount: int):
        super().__init__(f"This transaction must send at least '{amount / 1e18}' ether.")


class UnsupportedChainError(MulticallException):
    def __init__(self):
        super().__init__("Multicall not supported on this chain.")


class SafeClientException(ApeSafeException):
    pass


class ActionNotPerformedError(SafeClientException):
    def __init__(self, message: str):
        super().__init__(message)


class ClientResponseError(SafeClientException):
    def __init__(self, endpoint_url: str, response: "Response", message: Optional[str] = None):
        self.endpoint_url = endpoint_url
        self.response = response
        message = message or f"Exception when calling '{endpoint_url}':\n{response.text}"
        super().__init__(message)


class MultisigTransactionNotFoundError(ClientResponseError):
    def __init__(self, tx_hash: str, endpoint_url: str, response: "Response"):
        message = f"Multisig transaction '{tx_hash}' not found."
        super().__init__(endpoint_url, response, message=message)
