# API Reference

This page documents the key classes and methods available in the ape-safe Python API.

## SafeAccount

The `SafeAccount` class is the primary interface for interacting with a Safe.

```python
from ape import accounts
safe = accounts.load("my-safe")
```

### Properties

| Property | Description |
|----------|-------------|
| `address` | The Ethereum address of the Safe |
| `signers` | List of all authorized signers (owners) for the Safe |
| `confirmations_required` | Number of signatures needed (threshold) |
| `local_signers` | List of signers available in the local account store |
| `next_nonce` | Next on-chain nonce |
| `new_nonce` | Next available nonce including pending transactions |
| `contract` | The underlying Safe contract |
| `client` | The Safe Transaction Service client |
| `network` | The network where the Safe is deployed |

### Methods

#### Transaction Creation

```python
def create_safe_tx(
    to: str,
    value: int = 0,
    data: bytes = b"",
    operation: int = 0,
    safe_tx_gas: int = 0,
    base_gas: int = 0,
    gas_price: int = 0,
    gas_token: str = NULL_ADDRESS,
    refund_receiver: str = NULL_ADDRESS,
    signatures: Optional[Dict[str, str]] = None,
    nonce: Optional[int] = None,
) -> SafeTx
```

Creates a Safe transaction object.

#### Transaction Signing

```python
def sign_transaction(
    tx: SafeTx,
    submitter: Optional[AccountAPI] = None,
    impersonate: bool = False,
    submit: bool = True,
) -> Union[Receipt, SignatureError]
```

Signs a transaction with available local signers and optionally submits it.

#### Transaction Submission

```python
def submit_safe_tx(
    tx: SafeTx,
    submitter: Optional[AccountAPI] = None,
) -> Receipt
```

Submits a fully signed Safe transaction for on-chain execution.

#### Signature Collection

```python
def add_signatures(
    tx: SafeTx
) -> Dict[str, str]
```

Adds signatures from all available local signers.

#### Pending Transactions

```python
def pending_transactions(
    nonce: Optional[int] = None
) -> Iterator[Tuple[SafeTx, List[Dict]]]
```

Returns an iterator of pending transactions and their confirmations.

#### Rejection Creation

```python
def create_rejection(
    nonce: int
) -> SafeTx
```

Creates a rejection transaction (0 ETH self-send) for the given nonce.

#### Signer Management

```python
def compute_prev_signer(
    signer: str
) -> str
```

Computes the previous signer in the signers list (used for owner modifications).

## MultiSend

The `MultiSend` class allows batching multiple transactions.

```python
from ape_safe import multisend
txn = multisend.MultiSend()
```

### Methods

#### Adding Transactions

```python
def add(
    func_or_to,
    *args,
    **kwargs
) -> None
```

Adds a transaction to the batch. Can be called with:
- A contract function and its arguments
- A direct address, value, and data

#### Transaction Execution

```python
def __call__(
    sender: AccountAPI,
    **kwargs
) -> Receipt
```

Executes the MultiSend transaction using the specified sender.

#### Transaction Creation

```python
def as_transaction(
    sender: AccountAPI
) -> SafeTx
```

Returns a SafeTx object without executing it.

#### MultiSend Decoding

```python
def add_from_calldata(
    calldata: str
) -> None
```

Adds transactions from existing MultiSend calldata.

## SafeClient

The `SafeClient` class provides an interface to the Safe Transaction Service API.

```python
from ape_safe.client import SafeClient
client = SafeClient("0xSafeAddress", chain_id=1)
```

### Methods

#### Transaction Retrieval

```python
def get_transactions(
    confirmed: bool = True
) -> Iterator[SafeTxData]
```

Retrieves transactions from the Safe Transaction Service.

#### Confirmation Retrieval

```python
def get_confirmations(
    safe_tx_hash: str
) -> Iterator[Dict]
```

Retrieves confirmations for a specific Safe transaction.

#### Transaction Proposal

```python
def propose_transaction(
    safe_tx: SafeTx,
    signatures: Dict[str, str]
) -> Dict
```

Proposes a new transaction to the Safe Transaction Service.

#### Confirmation Addition

```python
def add_confirmation(
    safe_tx_hash: str,
    signature: str
) -> Dict
```

Adds a confirmation to an existing transaction.

## SafeTx

The `SafeTx` class represents a Safe transaction object.

```python
from ape_safe.client.types import SafeTx
tx = SafeTx(
    to="0xRecipient",
    value=1000000000000000000,  # 1 ETH
    data=b"",
    operation=0,
    safe_tx_gas=0,
    base_gas=0,
    gas_price=0,
    gas_token="0x0000000000000000000000000000000000000000",
    refund_receiver="0x0000000000000000000000000000000000000000",
    signatures={},
    safe_nonce=0,
    safe_address="0xSafeAddress",
    chain_id=1
)
```

### Properties

| Property | Description |
|----------|-------------|
| `to` | Recipient address |
| `value` | ETH value (in wei) |
| `data` | Transaction data |
| `operation` | Operation type (0=CALL, 1=DELEGATECALL) |
| `safe_tx_gas` | Gas for Safe transaction execution |
| `base_gas` | Gas for data and execution |
| `gas_price` | Gas price for the transaction |
| `gas_token` | Token used for gas refund |
| `refund_receiver` | Address for gas refund |
| `nonce` | Transaction nonce |
| `safe_address` | Address of the Safe |
| `chain_id` | Chain ID |
| `signatures` | Map of signer addresses to signatures |

### Methods

```python
def safe_tx_hash() -> str
```

Computes the EIP-712 hash for the transaction.

```python
def dump() -> Dict
```

Dumps the transaction to a dictionary.

## Utility Functions

```python
from ape_safe.utils import get_safe_tx_hash

# Get the EIP-712 hash for a transaction
tx_hash = get_safe_tx_hash(tx)
```