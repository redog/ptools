import json
from unittest.mock import patch

import pytest

from ptools.cli import main
from ptools.portage_adapter import MockPortageBackend


@pytest.fixture
def mock_backend():
    packages = {
        "sys-apps/portage": {
            "repo_versions": ["3.0.40", "3.0.50"],
            "installed_versions": ["3.0.40"],
            "iuse": ["build", "doc"],
            "effective_use": ["doc"],
            "installed_use": ["doc"],
        }
    }
    return MockPortageBackend(packages)


@patch("ptools.cli.sys.argv", ["ptools", "package", "resolve", "sys-apps/portage"])
@patch("ptools.cli.get_portage_backend")
def test_cli_package_resolve(mock_get_backend, mock_backend, capsys):
    mock_get_backend.return_value = mock_backend
    assert main() == 0
    captured = capsys.readouterr()
    assert "atom: sys-apps/portage" in captured.out
    assert "cp: sys-apps/portage" in captured.out


@patch("ptools.cli.sys.argv", ["ptools", "--json", "package", "resolve", "sys-apps/portage"])
@patch("ptools.cli.get_portage_backend")
def test_cli_package_resolve_json(mock_get_backend, mock_backend, capsys):
    mock_get_backend.return_value = mock_backend
    assert main() == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["atom"] == "sys-apps/portage"


@patch("ptools.cli.sys.argv", ["ptools", "package", "resolve", "invalid-package"])
@patch("ptools.cli.get_portage_backend")
def test_cli_package_not_found(mock_get_backend, mock_backend, capsys):
    mock_get_backend.return_value = mock_backend
    with pytest.raises(SystemExit) as excinfo:
        main()
    assert excinfo.value.code == 3
    captured = capsys.readouterr()
    assert "Package not found" in captured.err


@patch("ptools.cli.sys.argv", ["ptools", "use", "show", "sys-apps/portage"])
@patch("ptools.cli.get_portage_backend")
def test_cli_use_show(mock_get_backend, mock_backend, capsys):
    mock_get_backend.return_value = mock_backend
    assert main() == 0
    captured = capsys.readouterr()
    assert "iuse:" in captured.out
    assert "doc" in captured.out
