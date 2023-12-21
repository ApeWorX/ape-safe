def test_help(runner, cli):
    result = runner.invoke(cli, ["pending", "--help"], catch_exceptions=False)
    assert result.exit_code == 0, result.output


def test_list_no_safes(runner, cli, no_safes):
    result = runner.invoke(cli, ["pending", "list"])
    assert result.exit_code != 0, result.output
    assert "First, add a safe account using command" in result.output
    assert "ape safe add" in result.output


def test_list_no_txns(runner, cli, one_safe, safe):
    result = runner.invoke(cli, ["pending", "list"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert "There are no pending transactions" in result.output
