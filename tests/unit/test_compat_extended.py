from unittest.mock import patch

from ptools.compat.pkw import main as pkw_main
from ptools.compat.puse import main as puse_main


@patch("ptools.compat.puse.sys.argv", ["puse"])
@patch("ptools.compat.puse.argparse.ArgumentParser.print_help")
def test_puse_no_args(mock_help):
    assert puse_main() == 1
    mock_help.assert_called_once()


@patch("ptools.compat.pkw.sys.argv", ["pkw"])
@patch("ptools.compat.pkw.argparse.ArgumentParser.print_help")
def test_pkw_no_args(mock_help):
    assert pkw_main() == 1
    mock_help.assert_called_once()


@patch("ptools.compat.puse.sys.argv", ["puse", "app-editors/neovim"])
@patch("ptools.compat.puse.argparse.ArgumentParser.print_help")
def test_puse_no_action(mock_help):
    assert puse_main() == 1
    mock_help.assert_called_once()


@patch("ptools.compat.pkw.sys.argv", ["pkw", "app-editors/neovim"])
@patch("ptools.compat.pkw.argparse.ArgumentParser.print_help")
def test_pkw_no_action(mock_help):
    assert pkw_main() == 1
    mock_help.assert_called_once()


@patch("ptools.compat.puse.sys.argv", ["puse", "--remove", "--exact", "app-editors/neovim", "lua"])
@patch("ptools.compat.puse.subprocess.call")
def test_puse_remove_exact(mock_call):
    mock_call.return_value = 0
    assert puse_main() == 0
    mock_call.assert_called_with(["ptools", "use", "unset", "app-editors/neovim", "lua", "--exact"])


@patch("ptools.compat.pkw.sys.argv", ["pkw", "--remove", "--exact", "app-editors/neovim", "~amd64"])
@patch("ptools.compat.pkw.subprocess.call")
def test_pkw_remove_exact(mock_call):
    mock_call.return_value = 0
    assert pkw_main() == 0
    mock_call.assert_called_with(
        ["ptools", "keyword", "unset", "app-editors/neovim", "~amd64", "--exact"]
    )
