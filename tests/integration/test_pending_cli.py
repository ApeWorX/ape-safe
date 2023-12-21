def test_help(runner, cli):
    result = runner.invoke(cli, ["--help"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
