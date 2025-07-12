import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from functools import cached_property
from typing import TYPE_CHECKING, Optional, Union

import certifi
import requests
import urllib3
from ape.types import AddressType, HexBytes, MessageSignature
from eth_utils import keccak
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
    from ape.api import AccountAPI
    from requests import Response

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}


class BaseSafeClient(ABC):
    def __init__(self, base_url: str):
        self.base_url = base_url

    """Abstract methods"""

    @property
    @abstractmethod
    def safe_details(self) -> SafeDetails: ...

    @abstractmethod
    def get_next_nonce(self) -> int: ...

    @abstractmethod
    def _all_transactions(self) -> Iterator[SafeApiTxData]: ...

    @abstractmethod
    def get_safe_tx(self, safe_tx_hash: SafeTxID) -> SafeApiTxData: ...

    @abstractmethod
    def get_confirmations(self, safe_tx_hash: SafeTxID) -> Iterator[SafeTxConfirmation]: ...

    @abstractmethod
    def post_transaction(
        self, safe_tx: SafeTx, signatures: dict[AddressType, MessageSignature], **kwargs
    ): ...

    @abstractmethod
    def post_signatures(
        self,
        safe_tx_or_hash: Union[SafeTx, SafeTxID],
        signatures: dict[AddressType, MessageSignature],
    ): ...

    @abstractmethod
    def estimate_gas_cost(
        self, receiver: AddressType, value: int, data: bytes, operation: int = 0
    ) -> Optional[int]: ...

    """Shared methods"""

    def get_transactions(
        self,
        confirmed: Optional[bool] = None,
        starting_nonce: int = 0,
        ending_nonce: Optional[int] = None,
        filter_by_ids: Optional[set[SafeTxID]] = None,
        filter_by_missing_signers: Optional[set[AddressType]] = None,
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

    def create_delegate_message(self, delegate: AddressType) -> HexBytes:
        # NOTE: referencing https://github.com/safe-global/safe-eth-py/blob/
        # a0a5771622f143ee6301cfc381c5ed50832ff482/gnosis/safe/api/transaction_service_api.py#L34
        totp = int(time.time()) // 3600
        return HexBytes(keccak(text=(delegate + str(totp))))

    @abstractmethod
    def get_delegates(self) -> dict[AddressType, list[AddressType]]: ...

    @abstractmethod
    def add_delegate(self, delegate: AddressType, label: str, delegator: "AccountAPI"): ...

    @abstractmethod
    def remove_delegate(self, delegate: AddressType, delegator: "AccountAPI"): ...

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

    def _get(self, url: str, params: Optional[dict] = None, **kwargs) -> "Response":
        return self._request("GET", url, params=params, **kwargs)

    def _post(self, url: str, json: Optional[dict] = None, **kwargs) -> "Response":
        return self._request("POST", url, json=json, **kwargs)

    def _delete(self, url: str, json: Optional[dict] = None, **kwargs) -> "Response":
        return self._request("DELETE", url, json=json, **kwargs)

    @cached_property
    def _http(self):
        return urllib3.PoolManager(ca_certs=certifi.where())

    def _request(self, method: str, url: str, json: Optional[dict] = None, **kwargs) -> "Response":
        api_version = kwargs.pop("api_version", "v1")

        # NOTE: paged requests include full url already
        if url.startswith(self.base_url):
            api_url = url

        else:
            api_url = f"{self.base_url}/{api_version}{url}"

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
