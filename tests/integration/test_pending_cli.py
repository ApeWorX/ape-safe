from datetime import datetime

from ape_safe.client import ExecutedTxData


def test_help(runner, cli):
    result = runner.invoke(cli, ["pending", "--help"], catch_exceptions=False)
    assert result.exit_code == 0, result.output


def test_propose(runner, cli, safe_account, receiver, chain):
    nonce_at_start = safe_account.next_nonce
    cmd = (
        "pending",
        "propose",
        "--safe",
        safe_account.alias,
        "--to",
        receiver.address,
        "--value",
        "1",
        "--network",
        chain.provider.network_choice,
    )

    # Sender is required by the API even for initial proposal,
    # so it prompts the user.
    sender_input = f"{safe_account.alias}\n"

    result = runner.invoke(cli, cmd, input=sender_input)
    assert result.exit_code == 0

    # The nonce is the same because we did not execute.
    assert safe_account.next_nonce == nonce_at_start


def test_propose_with_sender(runner, cli, safe_account, receiver, chain):
    # First, fund the safe so the tx does not fail.
    receiver.transfer(safe_account, "1 ETH")

    nonce_at_start = safe_account.next_nonce
    cmd = (
        "pending",
        "propose",
        "--safe",
        safe_account.alias,
        "--to",
        receiver.address,
        "--value",
        "1",
        "--sender",
        receiver.address,
        "--network",
        chain.provider.network_choice,
    )
    result = runner.invoke(cli, cmd, catch_exceptions=False)
    assert result.exit_code == 0, result.output

    # The nonce is the same because we did not execute.
    assert safe_account.next_nonce == nonce_at_start


def test_propose_with_execute(runner, cli, safe_account, receiver, chain):
    # First, fund the safe so the tx does not fail.
    receiver.transfer(safe_account, "1 ETH")

    nonce_at_start = safe_account.next_nonce
    cmd = (
        "pending",
        "propose",
        "--safe",
        safe_account.alias,
        "--to",
        receiver.address,
        "--value",
        "1",
        "--sender",
        receiver.address,
        "--execute",
        "--network",
        chain.provider.network_choice,
    )
    result = runner.invoke(cli, cmd, catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert safe_account.next_nonce == nonce_at_start + 1


def test_list_no_safes(runner, cli, chain):
    result = runner.invoke(cli, ["pending", "list", "--network", chain.provider.network_choice])
    assert result.exit_code != 0, result.output
    assert "First, add a safe account using command" in result.output
    assert "ape safe add" in result.output


def test_list_no_txns(runner, cli, safe_account, chain):
    arguments = ("pending", "list", "--network", chain.provider.network_choice)
    result = runner.invoke(cli, arguments, catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert "There are no pending transactions" in result.output


def test_approve_transaction_not_found(runner, cli, safe_account, chain):
    tx_hash = "0x123"
    arguments = ("pending", "approve", tx_hash, "--network", chain.provider.network_choice)
    result = runner.invoke(
        cli,
        arguments,
        catch_exceptions=False,
    )
    assert result.exit_code != 0, result.output
    assert f"Pending transaction(s) '{tx_hash}' not found." in result.output


def test_approve(receiver, runner, cli, safe_account, chain):
    # First, fund the safe so the tx does not fail.
    receiver.transfer(safe_account, "1 ETH")
    tx_hash = "0x123"
    nonce = 1

    safe_account.client.transactions_by_nonce[nonce] = tx_hash
    safe_account.client.transactions[tx_hash] = ExecutedTxData(
        executionDate=datetime.now(),
        blockNumber=0,
        transactionHash=tx_hash,
        executor=receiver.address,
        isExecuted=False,
        isSuccessful=True,
        ethGasPrice=0,
        maxFeePerGas=1000,
        maxPriorityFeePerGas=1000,
        gasUsed=100,
        fee=10,
        origin="ape",
        dataDecoded=None,
        confirmationsRequired=0,
        safeTxHash=tx_hash,
        submissionDate=datetime.now(),
        modified=datetime.now(),
        nonce=nonce,
        refundReceiver=receiver.address,
        gasPrice=0,
        baseGas=0,
        safeTxGas=0,
        gasToken=receiver.address,
        operation=0,
        value=0,
        to=receiver.address,
        safe=safe_account.address,
    )

    arguments = ("pending", "approve", tx_hash, "--network", chain.provider.network_choice)
    result = runner.invoke(
        cli,
        arguments,
        catch_exceptions=False,
    )
    assert result.exit_code != 0, result.output
