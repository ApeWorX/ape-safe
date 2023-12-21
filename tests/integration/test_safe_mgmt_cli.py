def test_help(runner, cli):
    result = runner.invoke(cli, ["--help"], catch_exceptions=False)
    assert result.exit_code == 0, result.output


def test_list_no_safes(runner, cli, no_safes):
    result = runner.invoke(cli, ["list"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert "No Safes found" in result.output


def test_list_one_safe(runner, cli, one_safe):
    result = runner.invoke(cli, ["list"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert "Found 1 Safe" in result.output
    assert "0x5FbDB2315678afecb367f032d93F642f64180aa3" in result.output


def test_add_safe(runner, cli, no_safes, safe):
    result = runner.invoke(
        cli, ["add", safe.address, safe.alias], catch_exceptions=False, input="y\n"
    )
    assert result.exit_code == 0, result.output
    assert "SUCCESS" in result.output, result.output


def test_remove_safe(runner, cli, one_safe, safe):
    result = runner.invoke(cli, ["remove", safe.alias], catch_exceptions=False, input="y\n")
    assert result.exit_code == 0, result.output
    assert "SUCCESS" in result.output, result.output


def test_remove_safe_skip_confirmation(runner, cli, one_safe, safe):
    result = runner.invoke(cli, ["remove", safe.alias, "--yes"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert "SUCCESS" in result.output, result.output
