def test_help(runner, cli):
    result = runner.invoke(cli, "--help", catch_exceptions=False)
    assert result.exit_code == 0, result.output


def test_list_no_safes(runner, cli):
    result = runner.invoke(cli, "list", catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert "No Safes found" in result.output


def test_list_one_safe(runner, cli, safe_account):
    result = runner.invoke(cli, "list", catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert "Found 1 Safe" in result.output
    assert safe_account.address in result.output


def test_list_network_not_connected(runner, cli, safe_account):
    result = runner.invoke(
        cli, ("list", "--network", "ethereum:local:test"), catch_exceptions=False
    )
    assert result.exit_code == 0, result.output
    assert "Found 1 Safe" in result.output
    assert safe_account.address in result.output
    assert "not connected" in result.output


def test_list_network_connected(runner, cli, safe_account):
    result = runner.invoke(
        cli, ("list", "--network", "ethereum:local:foundry"), catch_exceptions=False
    )
    assert result.exit_code == 0, result.output
    assert "Found 1 Safe" in result.output
    assert safe_account.address in result.output
    assert "not connected" not in result.output


def test_add_safe(runner, cli, safe, chain, safe_container):
    result = runner.invoke(
        cli,
        ("add", safe.address, safe.alias, "--network", chain.provider.network_choice),
        catch_exceptions=False,
        input="y\n",
    )
    assert result.exit_code == 0, result.output

    result = runner.invoke(cli, "list")
    assert safe.address in result.output, result.output
    safe_container.delete_account(safe.alias)


def test_remove_safe(runner, cli, safe_account):
    safe_address = safe_account.address
    result = runner.invoke(cli, ("remove", safe_account.alias), catch_exceptions=False, input="y\n")
    assert result.exit_code == 0, result.output

    result = runner.invoke(cli, "list")
    assert safe_address not in result.output, result.output


def test_remove_safe_skip_confirmation(runner, cli, safe_account):
    safe_address = safe_account.address
    result = runner.invoke(cli, ("remove", safe_account.alias, "--yes"), catch_exceptions=False)
    assert result.exit_code == 0, result.output

    result = runner.invoke(cli, "list")
    assert safe_address not in result.output, result.output
