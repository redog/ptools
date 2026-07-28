import pytest

from ptools.errors import AmbiguousPackageError, PackageNotFoundError
from ptools.portage_adapter import MockPortageBackend


@pytest.fixture
def mock_backend():
    packages = {
        "sys-apps/portage": {
            "repo_versions": ["3.0.40", "3.0.50"],
            "installed_versions": ["3.0.40"],
            "iuse": [
                "build",
                "doc",
                "epydoc",
                "gentoo-dev",
                "ipc",
                "native-extensions",
                "rsync-verify",
                "selinux",
                "test",
                "xattr",
            ],
            "effective_use": ["ipc", "native-extensions", "rsync-verify", "xattr"],
            "installed_use": ["ipc", "native-extensions", "xattr"],
        },
        "app-editors/neovim": {
            "repo_versions": ["0.9.5", "0.10.0"],
            "installed_versions": [],
            "iuse": ["lua", "python", "nvui"],
            "effective_use": ["lua"],
            "installed_use": [],
        },
    }
    return MockPortageBackend(packages)


def test_mock_backend_resolve_exact(mock_backend):
    res = mock_backend.resolve("=app-editors/neovim-0.9.5")
    assert res.cp == "app-editors/neovim"
    assert res.cpv == "app-editors/neovim-0.9.5"
    assert "app-editors/neovim-0.9.5" in res.repository_versions


def test_mock_backend_resolve_unqualified_ambiguous():
    backend = MockPortageBackend({"sys-apps/test": {}, "dev-util/test": {}})
    with pytest.raises(AmbiguousPackageError):
        backend.resolve("test")


def test_mock_backend_resolve_unqualified_success(mock_backend):
    res = mock_backend.resolve("neovim")
    assert res.cp == "app-editors/neovim"


def test_mock_backend_resolve_not_found(mock_backend):
    with pytest.raises(PackageNotFoundError):
        mock_backend.resolve("app-editors/vim")


def test_mock_backend_use_flags(mock_backend):
    assert "lua" in mock_backend.effective_use("app-editors/neovim")
    assert "ipc" in mock_backend.installed_use("sys-apps/portage")
    assert "python" in mock_backend.iuse("app-editors/neovim")
