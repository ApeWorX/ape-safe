from ape_safe.utils import order_by_signer


def test_order_by_signer_empty():
    assert order_by_signer({}) == []


def test_order_by_signer_1_sig(accounts):
    signature = accounts[0].sign_message("hello")
    signature_map = {accounts[0].address: signature}
    assert order_by_signer(signature_map) == [signature]


def test_order_by_signer_n_sigs(accounts):
    # NOTE: acct_0 > acct_1 by integer value.
    acct_0 = accounts[0]  # 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
    acct_1 = accounts[1]  # 0x70997970C51812dc3A010C7d01b50e0d17dc79C8

    signature_0 = acct_0.sign_message("hello")
    signature_1 = acct_1.sign_message("hello")

    # Ensure all orders of the dict work.
    signature_map_0 = {acct_0.address: signature_0, acct_1.address: signature_1}
    signature_map_1 = {acct_1.address: signature_1, acct_0.address: signature_0}

    # We expect the signatures to be sorted in ascending order by the
    # signer's address. Here, acct_0 > acct_1 so acct_1's signature is
    # the first and acct_0's is the latter.
    expected = [signature_1, signature_0]
    act_0 = order_by_signer(signature_map_0)
    act_1 = order_by_signer(signature_map_1)
    assert act_0 == act_1 == expected
