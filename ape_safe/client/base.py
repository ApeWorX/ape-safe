from abc import ABC, abstractmethod
from collections.abc import Iterator
from functools import cached_property
from typing import TYPE_CHECKING, Optional, Union

import certifi
import requests
import urllib3
from requests.adapters import HTTPAdapter

from ape_safe.client.types import (
    ExecutedTxData,
    SafeApiTxData,
    SafeDetails,
    SafeTx,
    SafeTxConfirmation,
    SafeTxID,
    UnexecutedTxData,
)
from ape_safe.exceptions import ClientResponseError

if TYPE_CHECKING:
    from ape.types import AddressType, MessageSignature
    from requests import Response

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}


class BaseSafeClient(ABC):
    def __init__(self, transaction_service_url: str):
        self.transaction_service_url = transaction_service_url

    """Abstract methods"""

    @property
    @abstractmethod
    def safe_details(self) -> SafeDetails: ...

    @abstractmethod
    def get_next_nonce(self) -> int: ...

    @abstractmethod
    def _all_transactions(self) -> Iterator[SafeApiTxData]: ...

    @abstractmethod
    def get_confirmations(self, safe_tx_hash: SafeTxID) -> Iterator[SafeTxConfirmation]: ...

    @abstractmethod
    def post_transaction(
        self, safe_tx: SafeTx, signatures: dict["AddressType", "MessageSignature"], **kwargs
    ): ...

    @abstractmethod
    def post_signatures(
        self,
        safe_tx_or_hash: Union[SafeTx, SafeTxID],
        signatures: dict["AddressType", "MessageSignature"],
    ): ...

    @abstractmethod
    def estimate_gas_cost(
        self, receiver: "AddressType", value: int, data: bytes, operation: int = 0
    ) -> Optional[int]: ...

    """Shared methods"""

    def get_transactions(
        self,
        confirmed: Optional[bool] = None,
        starting_nonce: int = 0,
        ending_nonce: Optional[int] = None,
        filter_by_ids: Optional[set[SafeTxID]] = None,
        filter_by_missing_signers: Optional[set["AddressType"]] = None,
    ) -> Iterator[SafeApiTxData]:
        """
        confirmed: Confirmed if True, not confirmed if False, both if None
        """
        next_nonce = self.get_next_nonce()

        # NOTE: We loop backwards.
        for txn in self._all_transactions():
            if ending_nonce is not None and txn.nonce > ending_nonce:
                # NOTE: Skip all largest nonces first
                continue

            elif txn.nonce < starting_nonce:
                break  # NOTE: order is largest nonce to smallest, so safe to break here

            is_confirmed = len(txn.confirmations) >= txn.confirmations_required

            if confirmed is not None:
                if not confirmed and isinstance(txn, ExecutedTxData):
                    break  # NOTE: Break at the first executed transaction

                elif confirmed and not is_confirmed:
                    continue  # NOTE: Skip not confirmed transactions

            # NOTE: use `type(txn) is ...` because ExecutedTxData is a subclass of UnexecutedTxData
            if txn.nonce < next_nonce and type(txn) is UnexecutedTxData:
                continue  # NOTE: Skip orphaned transactions

            if filter_by_ids and txn.safe_tx_hash not in filter_by_ids:
                continue  # NOTE: Skip transactions not in the filter

            if filter_by_missing_signers and filter_by_missing_signers.issubset(
                set(conf.owner for conf in txn.confirmations)
            ):
                # NOTE: Skip if all signers from `filter_by_missing_signers`
                #       are in `txn.confirmations`
                continue

            yield txn

    """Request methods"""

    @cached_property
    def session(self) -> requests.Session:
        session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=10,  # Doing all the connections to the same url
            pool_maxsize=100,  # Number of concurrent connections
            pool_block=False,
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _get(self, url: str) -> "Response":
        return self._request("GET", url)

    def _post(self, url: str, json: Optional[dict] = None, **kwargs) -> "Response":
        return self._request("POST", url, json=json, **kwargs)

    @cached_property
    def _http(self):
        return urllib3.PoolManager(ca_certs=certifi.where())

    def _request(self, method: str, url: str, json: Optional[dict] = None, **kwargs) -> "Response":
        # NOTE: paged requests include full url already
        if url.startswith(f"{self.transaction_service_url}/api/v1/"):
            api_url = url
        else:
            # **WARNING**: The trailing slash in the URL is CRITICAL!
            # If you remove it, things will not work as expected.
            api_url = f"{self.transaction_service_url}/api/v1/{url}/"
        do_fail = not kwargs.pop("allow_failure", False)

        # Use `or 10` to handle when None is explicit.
        kwargs["timeout"] = kwargs.get("timeout") or 10

        # Add default headers
        headers = kwargs.get("headers", {})
        kwargs["headers"] = {**DEFAULT_HEADERS, **headers}
        response = self.session.request(method, api_url, json=json, **kwargs)

        if not response.ok and do_fail:
            raise ClientResponseError(api_url, response)

        return response
