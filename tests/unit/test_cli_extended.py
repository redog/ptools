import json
from unittest.mock import MagicMock, patch

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


@patch("ptools.cli.sys.argv", ["ptools", "package", "versions", "sys-apps/portage"])
@patch("ptools.cli.get_portage_backend")
def test_cli_package_versions(mock_get_backend, mock_backend, capsys):
    mock_get_backend.return_value = mock_backend
    assert main() == 0
    captured = capsys.readouterr()
    assert "installed" in captured.out
    assert "repository" in captured.out


@patch("ptools.cli.sys.argv", ["ptools", "keyword", "show", "sys-apps/portage"])
@patch("ptools.cli.get_portage_backend")
def test_cli_keyword_show(mock_get_backend, mock_backend, capsys):
    mock_get_backend.return_value = mock_backend
    assert main() == 0
    captured = capsys.readouterr()
    assert "Keyword state analysis deferred" in captured.out


@patch("ptools.cli.sys.argv", ["ptools", "use", "set", "sys-apps/portage", "doc", "--dry-run"])
@patch("ptools.cli.get_portage_backend")
def test_cli_use_set(mock_get_backend, mock_backend, capsys):
    mock_get_backend.return_value = mock_backend
    assert main() == 0
    captured = capsys.readouterr()
    assert "use.set" in captured.out


@patch(
    "ptools.cli.sys.argv",
    ["ptools", "keyword", "set", "sys-apps/portage", "--testing", "--dry-run"],
)
@patch("ptools.cli.get_portage_backend")
def test_cli_keyword_set_testing(mock_get_backend, mock_backend, capsys):
    mock_get_backend.return_value = mock_backend
    assert main() == 0
    captured = capsys.readouterr()
    assert "~amd64" in captured.out


@patch("ptools.cli.sys.argv", ["ptools", "use", "set", "ambiguous_name", "doc"])
@patch("ptools.cli.get_portage_backend")
def test_cli_ambiguous_package(mock_get_backend, capsys):
    mock = MagicMock()
    from ptools.errors import AmbiguousPackageError

    mock.resolve.side_effect = AmbiguousPackageError("Ambiguous")
    mock_get_backend.return_value = mock
    with pytest.raises(SystemExit) as excinfo:
        main()
    assert excinfo.value.code == 4


@patch("ptools.cli.sys.argv", ["ptools", "use", "set", "error_name", "doc"])
@patch("ptools.cli.get_portage_backend")
def test_cli_generic_error(mock_get_backend, capsys):
    mock = MagicMock()
    from ptools.errors import PtoolsError

    mock.resolve.side_effect = PtoolsError("Error")
    mock_get_backend.return_value = mock
    with pytest.raises(SystemExit) as excinfo:
        main()
    assert excinfo.value.code == 1


@patch("ptools.cli.sys.argv", ["ptools", "--json", "package", "resolve", "invalid_name"])
@patch("ptools.cli.get_portage_backend")
def test_cli_json_error_not_found(mock_get_backend, capsys):
    mock = MagicMock()
    from ptools.errors import PackageNotFoundError

    mock.resolve.side_effect = PackageNotFoundError("Not found")
    mock_get_backend.return_value = mock
    assert main() == 3
    captured = capsys.readouterr()
    assert "error" in json.loads(captured.out)


@patch("ptools.cli.sys.argv", ["ptools", "--json", "use", "set", "ambiguous", "doc"])
@patch("ptools.cli.get_portage_backend")
def test_cli_json_error_ambiguous(mock_get_backend, capsys):
    mock = MagicMock()
    from ptools.errors import AmbiguousPackageError

    mock.resolve.side_effect = AmbiguousPackageError("Ambiguous")
    mock_get_backend.return_value = mock
    assert main() == 4
    captured = capsys.readouterr()
    assert "error" in json.loads(captured.out)


@patch("ptools.cli.sys.argv", ["ptools", "--json", "use", "set", "error_pkg", "doc"])
@patch("ptools.cli.get_portage_backend")
def test_cli_json_error_generic(mock_get_backend, capsys):
    mock = MagicMock()
    from ptools.errors import PtoolsError

    mock.resolve.side_effect = PtoolsError("Generic")
    mock_get_backend.return_value = mock
    assert main() == 1
    captured = capsys.readouterr()
    assert "error" in json.loads(captured.out)
