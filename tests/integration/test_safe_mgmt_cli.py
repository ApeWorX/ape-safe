def test_help(runner, cli):
    result = runner.invoke(cli, "--help", catch_exceptions=False)
    assert result.exit_code == 0, result.output


def test_list_no_safes(runner, cli, no_safes):
    result = runner.invoke(cli, "list", catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert "No Safes found" in result.output


def test_list_one_safe(runner, cli, one_safe):
    result = runner.invoke(cli, "list", catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert "Found 1 Safe" in result.output
    assert one_safe.address in result.output


def test_list_network_not_connected(runner, cli, one_safe):
    result = runner.invoke(
        cli, ("list", "--network", "ethereum:local:test"), catch_exceptions=False
    )
    assert result.exit_code == 0, result.output
    assert "Found 1 Safe" in result.output
    assert one_safe.address in result.output
    assert "not connected" in result.output


def test_list_network_connected(runner, cli, one_safe):
    result = runner.invoke(
        cli, ("list", "--network", "ethereum:local:foundry"), catch_exceptions=False
    )
    assert result.exit_code == 0, result.output
    assert "Found 1 Safe" in result.output
    assert one_safe.address in result.output
    assert "not connected" not in result.output


def test_add_safe(runner, cli, no_safes, safe, chain):
    result = runner.invoke(
        cli,
        ("add", safe.address, safe.alias, "--network", chain.provider.network_choice),
        catch_exceptions=False,
        input="y\n",
    )
    assert result.exit_code == 0, result.output
    assert "SUCCESS" in result.output, result.output


def test_remove_safe(runner, cli, one_safe, safe):
    result = runner.invoke(cli, ("remove", safe.alias), catch_exceptions=False, input="y\n")
    assert result.exit_code == 0, result.output
    assert "SUCCESS" in result.output, result.output


def test_remove_safe_skip_confirmation(runner, cli, one_safe, safe):
    result = runner.invoke(cli, ("remove", safe.alias, "--yes"), catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert "SUCCESS" in result.output, result.output
