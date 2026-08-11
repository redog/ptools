from unittest.mock import patch

from ptools.compat.pkw import main as pkw_main
from ptools.compat.puse import main as puse_main


@patch("ptools.compat.puse.sys.argv", ["puse", "--show", "app-editors/neovim"])
@patch("ptools.compat.puse.subprocess.call")
def test_puse_show(mock_call):
    mock_call.return_value = 0
    assert puse_main() == 0
    mock_call.assert_called_with(["ptools", "use", "show", "app-editors/neovim"])


@patch("ptools.compat.puse.sys.argv", ["puse", "--change", "--any", "app-editors/neovim", "lua"])
@patch("ptools.compat.puse.subprocess.call")
def test_puse_change(mock_call):
    mock_call.return_value = 0
    assert puse_main() == 0
    mock_call.assert_called_with(["ptools", "use", "set", "app-editors/neovim", "lua"])


@patch(
    "ptools.compat.puse.sys.argv",
    ["puse", "--change", "--any", "--not", "app-editors/neovim", "lua"],
)
@patch("ptools.compat.puse.subprocess.call")
def test_puse_change_not(mock_call):
    mock_call.return_value = 0
    assert puse_main() == 0
    mock_call.assert_called_with(["ptools", "use", "set", "app-editors/neovim", "-lua"])


@patch("ptools.compat.pkw.sys.argv", ["pkw", "--change", "--any", "app-editors/neovim"])
@patch("ptools.compat.pkw.subprocess.call")
def test_pkw_change(mock_call):
    mock_call.return_value = 0
    assert pkw_main() == 0
    mock_call.assert_called_with(["ptools", "keyword", "set", "app-editors/neovim", "--testing"])


@patch("ptools.compat.pkw.sys.argv", ["pkw", "--change", "--unall", "app-editors/neovim"])
@patch("ptools.compat.pkw.subprocess.call")
def test_pkw_change_unall(mock_call):
    mock_call.return_value = 0
    assert pkw_main() == 0
    mock_call.assert_called_with(["ptools", "keyword", "set", "app-editors/neovim", "-*"])
